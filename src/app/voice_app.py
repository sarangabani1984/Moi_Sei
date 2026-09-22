import html

import streamlit as st

from db import (
    get_connection,
    search_contributions_by_amount,
    search_family_contributions,
    search_family_contributions_many,
)
from voice_ai import (
    build_tamil_contribution_response,
    parse_contribution_query_with_litellm,
    text_to_speech_openai,
    transcribe_audio_with_whisper,
)


st.set_page_config(
    page_title="Moi Sei Voice Assistant",
    page_icon="🎙️",
    layout="centered",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #18231f;
        --muted: #5c6963;
        --paper: #f5f1e8;
        --accent: #ba3f2d;
        --line: #d8d0c2;
    }
    .stApp {
        color: var(--ink);
        background:
            linear-gradient(90deg, rgba(186, 63, 45, .06) 1px, transparent 1px),
            linear-gradient(rgba(186, 63, 45, .06) 1px, transparent 1px),
            var(--paper);
        background-size: 32px 32px;
    }
    h1, h2, h3 { font-family: Georgia, "Times New Roman", serif; letter-spacing: 0; }
    p, label, button, input { font-family: "Trebuchet MS", sans-serif; letter-spacing: 0; }
    div[data-testid="stAudioInput"] {
        border-top: 3px solid var(--accent);
        border-bottom: 1px solid var(--line);
        padding: 1.25rem 0;
    }
    div[data-testid="stMetric"] {
        border-left: 3px solid var(--accent);
        padding-left: 1rem;
    }
    div[data-testid="stMetricLabel"] p {
        color: var(--muted) !important;
        font-weight: 700;
    }
    div[data-testid="stMetricValue"] {
        color: var(--ink) !important;
    }
    .result-name { font-family: Georgia, serif; font-size: 1.35rem; font-weight: 700; }
    .result-place { color: var(--muted); margin-bottom: .75rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Moi Sei Voice Assistant")
st.caption("Ask about a family, place, contribution amount, or contributor count")


def reset_voice_question():
    st.session_state["voice_input_generation"] = (
        st.session_state.get("voice_input_generation", 0) + 1
    )
    for key in (
        "voice_transcript",
        "voice_query_plan",
        "voice_results",
    ):
        st.session_state.pop(key, None)

try:
    get_connection()
except Exception as error:
    st.error("Could not connect to the local SQL Server database.")
    st.code(str(error))
    st.stop()

st.button(
    "New question / Reset",
    on_click=reset_voice_question,
    use_container_width=True,
)

with st.expander("⚙️ Model testing (LiteLLM)", expanded=False):
    voice_model = st.selectbox(
        "Model used to understand your question",
        options=["gpt-4o-mini", "groq/openai/gpt-oss-20b", "groq/openai/gpt-oss-120b"],
        index=0,
        help="Compare accuracy across providers. Needs the matching API key in secrets.toml.",
    )

input_generation = st.session_state.get("voice_input_generation", 0)
audio = st.audio_input(
    "Ask your contribution question",
    sample_rate=16000,
    key=f"voice_audio_input_{input_generation}",
)
typed_query = st.text_input(
    "Or type the request",
    placeholder="Who contributed more than 10000?",
    key=f"voice_typed_query_{input_generation}",
)

if st.button("Find contribution", type="primary", use_container_width=True):
    transcript = typed_query.strip()
    if audio is not None:
        with st.spinner("Converting speech to text..."):
            success, transcript_or_error = transcribe_audio_with_whisper(audio.getvalue())
        if not success:
            st.error(transcript_or_error)
            st.stop()
        transcript = transcript_or_error.strip()

    if not transcript:
        st.warning("Record a message or type a request.")
        st.stop()

    st.session_state["voice_transcript"] = transcript
    with st.spinner("Understanding your question..."):
        parsed = parse_contribution_query_with_litellm(transcript, model=voice_model)
    if parsed.get("error"):
        st.subheader("Recognized request")
        st.write(transcript)
        st.error(parsed["error"])
        st.stop()

    st.session_state["voice_query_plan"] = parsed
    if parsed["query_type"] == "amount_filter":
        st.session_state["voice_results"] = search_contributions_by_amount(
            parsed["amount"], parsed["operator"]
        )
    else:
        st.session_state["voice_results"] = search_family_contributions_many(
            parsed.get("husband_names", [parsed["husband_name"]]),
            parsed["current_place"],
        )

if "voice_transcript" in st.session_state:
    st.subheader("Recognized request")
    st.write(st.session_state["voice_transcript"])

if "voice_results" in st.session_state:
    query_plan = st.session_state["voice_query_plan"]
    with st.expander("Processing details: Voice → Text → SQL", expanded=True):
        st.markdown("**1. Speech-to-text output**")
        st.code(st.session_state["voice_transcript"], language="text")
        st.markdown("**2. Parsed search values**")
        st.json({key: value for key, value in query_plan.items() if key != "error"})
        st.markdown("**3. Parameterized SQL preview**")
        if query_plan["query_type"] == "amount_filter":
            operator_sql = {
                "eq": "=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="
            }[query_plan["operator"]]
            sql_preview = f"""SELECT u.husband_name, u.current_place,
       COUNT(DISTINCT je.transaction_id) AS contribution_count,
       SUM(je.amount) AS total_contributed
FROM dbo.users u
JOIN dbo.journal_entries je ON je.user_id = u.id
WHERE u.is_active = 1
  AND je.entry_type = 'CONTRIBUTED'
  AND je.amount {operator_sql} ?
GROUP BY u.id, u.husband_name, u.wife_name, u.current_place
ORDER BY u.husband_name;"""
            bound_values = [query_plan["amount"]]
        else:
            parsed_husband_names = query_plan.get(
                "husband_names", [query_plan["husband_name"]]
            )
            parsed_current_place = query_plan["current_place"]
            sql_preview = """-- Executed once for each parsed husband name, then deduplicated by user ID
SELECT
    u.husband_name,
    u.wife_name,
    u.current_place,
    COUNT(DISTINCT CASE WHEN je.entry_type = 'CONTRIBUTED'
                        THEN je.transaction_id END) AS contribution_count,
    COALESCE(SUM(CASE WHEN je.entry_type = 'CONTRIBUTED'
                      THEN je.amount ELSE 0 END), 0) AS total_contributed
FROM dbo.users u
LEFT JOIN dbo.journal_entries je ON je.user_id = u.id
WHERE u.is_active = 1
  AND (? = '' OR u.husband_name LIKE ? OR u.search_alias LIKE ?)
  AND (? = '' OR u.current_place LIKE ?)
GROUP BY u.id, u.husband_name, u.wife_name, u.current_place
ORDER BY u.husband_name;"""
            bound_values = [
                {
                    "husband_name": name,
                    "name_pattern": f"%{name}%",
                    "current_place": parsed_current_place,
                    "place_pattern": f"%{parsed_current_place}%",
                }
                for name in parsed_husband_names
            ]
        st.code(sql_preview, language="sql")
        st.markdown("**4. Bound parameter values**")
        st.json(bound_values)
        st.caption("The values are bound safely; recognized speech is never executed as SQL code.")

    if query_plan["query_type"] == "family_lookup":
        husband_name = st.text_input(
            "Husband names (comma separated)",
            value=", ".join(query_plan.get("husband_names", [query_plan["husband_name"]])),
        )
        current_place = st.text_input(
            "Current place",
            value=query_plan["current_place"],
        )
        if st.button("Search with corrected details", use_container_width=True):
            husband_names = [name.strip() for name in husband_name.split(",") if name.strip()]
            query_plan["husband_names"] = husband_names
            query_plan["husband_name"] = husband_names[0] if husband_names else ""
            query_plan["current_place"] = current_place.strip()
            st.session_state["voice_results"] = search_family_contributions_many(
                husband_names, current_place
            )
            st.rerun()

    results = st.session_state["voice_results"]
    st.divider()
    if not results:
        response_text = build_tamil_contribution_response(results, query_plan)
        st.warning(response_text)
    else:
        st.subheader("Contribution result")
        st.metric("Matching people", len(results))
        if query_plan["response_mode"] == "list":
            for result in results:
                display_name = html.escape(str(result["husband_name"]))
                display_place = html.escape(str(result.get("current_place") or "Place not recorded"))
                st.markdown(
                    f'<div class="result-name">{display_name}</div>'
                    f'<div class="result-place">{display_place}</div>',
                    unsafe_allow_html=True,
                )
                metric_left, metric_right = st.columns(2)
                metric_left.metric("Matching amount", f'₹{result["total_contributed"]:,.2f}')
                metric_right.metric("Contributions", result["contribution_count"])

        response_text = build_tamil_contribution_response(results, query_plan)

    st.subheader("தமிழ் பதில்")
    st.write(response_text)
    spoken_response = build_tamil_contribution_response(results, query_plan, spoken=True)
    speech_success, speech_audio = text_to_speech_openai(spoken_response)
    if speech_success:
        st.audio(speech_audio, format="audio/mp3", autoplay=True)
        st.caption("ஒலி தானாக இயங்கவில்லை என்றால் Play பொத்தானை அழுத்தவும்.")
    else:
        st.error("தமிழ் குரல் பதிலை உருவாக்க முடியவில்லை. மேலே உள்ள பதிலைப் படிக்கலாம்.")