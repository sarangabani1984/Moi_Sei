import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

// Use localhost for web, 10.0.2.2 for Android emulator
const apiBaseUrl = String.fromEnvironment(
  'MOI_SEI_API_URL',
  defaultValue: 'http://localhost:8000',
);

void main() {
  runApp(const MoiSeiApp());
}

class MoiSeiApp extends StatelessWidget {
  const MoiSeiApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Moi Sei',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepOrange),
        useMaterial3: true,
      ),
      home: const LoginScreen(),
    );
  }
}

class Family {
  final int id;
  final String husbandName;
  final String? wifeName;
  final String phoneNumber;
  final String? place;

  Family({
    required this.id,
    required this.husbandName,
    this.wifeName,
    required this.phoneNumber,
    this.place,
  });

  factory Family.fromJson(Map<String, dynamic> json) {
    return Family(
      id: json['id'],
      husbandName: json['husband_name'],
      wifeName: json['wife_name'],
      phoneNumber: json['phone_number'],
      place: json['place'],
    );
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final phoneController = TextEditingController();
  final passwordController = TextEditingController();
  bool isLoading = false;
  String? errorMessage;

  @override
  void dispose() {
    phoneController.dispose();
    passwordController.dispose();
    super.dispose();
  }

  Future<void> signIn() async {
    setState(() {
      isLoading = true;
      errorMessage = null;
    });

    try {
      final response = await http.post(
        Uri.parse('$apiBaseUrl/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'phone_number': phoneController.text.trim(),
          'password': passwordController.text,
        }),
      );

      if (!mounted) return;
      if (response.statusCode == 200) {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        final family = Family.fromJson(body['family']);
        
        // Navigate to dashboard
        if (mounted) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (context) => DashboardScreen(family: family),
            ),
          );
        }
      } else {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        setState(() {
          errorMessage = body['detail']?.toString() ?? 'Login failed.';
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        errorMessage = 'Cannot connect to API at $apiBaseUrl.';
      });
    } finally {
      if (mounted) {
        setState(() {
          isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Moi Sei')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'Family Login',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 20),
                    TextField(
                      controller: phoneController,
                      keyboardType: TextInputType.phone,
                      decoration: const InputDecoration(
                        labelText: 'Registered phone number',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: passwordController,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: 'Portal password',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: isLoading ? null : signIn,
                      child: Text(isLoading ? 'Signing in...' : 'Sign In'),
                    ),
                    if (errorMessage != null) ...[
                      const SizedBox(height: 16),
                      Text(
                        errorMessage!,
                        style: TextStyle(color: Theme.of(context).colorScheme.error),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class DashboardScreen extends StatefulWidget {
  final Family family;

  const DashboardScreen({super.key, required this.family});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int currentTabIndex = 0;
  late Future<Map<String, dynamic>> transactionData;
  late Future<List<dynamic>> contributionsData;
  late Future<List<dynamic>> receiptsData;
  late Future<List<dynamic>> upcomingEventsData;
  late Future<List<dynamic>> partnerHistoryData;
  late Future<List<dynamic>> myEventsData;

  final eventNameController = TextEditingController();
  final eventDateController = TextEditingController();
  final eventPlaceController = TextEditingController();

  @override
  void initState() {
    super.initState();
    // Load sequentially to avoid overwhelming the SQL Server connection pool
    // (parallel requests cause 500 errors on SQL Server Express).
    transactionData = _loadAllSequentially();
    contributionsData = _contributionsCompleter.future;
    receiptsData = _receiptsCompleter.future;
    upcomingEventsData = _upcomingEventsCompleter.future;
    partnerHistoryData = _partnerHistoryCompleter.future;
    myEventsData = _myEventsCompleter.future;
  }

  final _contributionsCompleter = Completer<List<dynamic>>();
  final _receiptsCompleter = Completer<List<dynamic>>();
  final _upcomingEventsCompleter = Completer<List<dynamic>>();
  final _partnerHistoryCompleter = Completer<List<dynamic>>();
  final _myEventsCompleter = Completer<List<dynamic>>();

  Future<Map<String, dynamic>> _loadAllSequentially() async {
    final trans = await fetchTransactions();

    try {
      _contributionsCompleter.complete(await fetchContributions());
    } catch (e) {
      _contributionsCompleter.completeError(e);
    }
    try {
      _receiptsCompleter.complete(await fetchReceipts());
    } catch (e) {
      _receiptsCompleter.completeError(e);
    }
    try {
      _upcomingEventsCompleter.complete(await fetchUpcomingEvents());
    } catch (e) {
      _upcomingEventsCompleter.completeError(e);
    }
    try {
      _partnerHistoryCompleter.complete(await fetchPartnerHistory());
    } catch (e) {
      _partnerHistoryCompleter.completeError(e);
    }
    try {
      _myEventsCompleter.complete(await fetchMyEvents());
    } catch (e) {
      _myEventsCompleter.completeError(e);
    }

    return trans;
  }

  @override
  void dispose() {
    eventNameController.dispose();
    eventDateController.dispose();
    eventPlaceController.dispose();
    super.dispose();
  }

  Future<Map<String, dynamic>> fetchTransactions() async {
    try {
      final response = await http.get(
        Uri.parse('$apiBaseUrl/family/${widget.family.id}/transactions'),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to load transactions');
      }
    } catch (e) {
      throw Exception('Could not connect to API');
    }
  }

  Future<List<dynamic>> fetchContributions() async {
    try {
      final response = await http.get(
        Uri.parse('$apiBaseUrl/family/${widget.family.id}/contributions'),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['contributions'] ?? [];
      } else {
        throw Exception('Failed to load contributions: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Error loading contributions: $e');
    }
  }

  Future<List<dynamic>> fetchReceipts() async {
    try {
      final response = await http.get(
        Uri.parse('$apiBaseUrl/family/${widget.family.id}/receipts'),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['receipts'] ?? [];
      } else {
        throw Exception('Failed to load receipts: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Error loading receipts: $e');
    }
  }

  Future<List<dynamic>> fetchUpcomingEvents() async {
    try {
      final response = await http.get(
        Uri.parse('$apiBaseUrl/family/${widget.family.id}/upcoming-events'),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['events'] ?? [];
      } else {
        throw Exception('Failed to load events: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Error loading upcoming events: $e');
    }
  }

  Future<List<dynamic>> fetchPartnerHistory() async {
    try {
      final response = await http.get(
        Uri.parse('$apiBaseUrl/family/${widget.family.id}/partner-history'),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['partners'] ?? [];
      } else {
        throw Exception('Failed to load partner history: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Error loading partner history: $e');
    }
  }

  Future<List<dynamic>> fetchMyEvents() async {
    try {
      final response = await http.get(
        Uri.parse('$apiBaseUrl/family/${widget.family.id}/events'),
        headers: {'Content-Type': 'application/json'},
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['events'] ?? [];
      } else {
        throw Exception('Failed to load my events: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Error loading my events: $e');
    }
  }

  Future<void> createEvent() async {
    if (eventNameController.text.isEmpty || 
        eventDateController.text.isEmpty || 
        eventPlaceController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please fill all required fields')),
      );
      return;
    }

    try {
      final response = await http.post(
        Uri.parse('$apiBaseUrl/family/${widget.family.id}/event'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'event_name': eventNameController.text,
          'event_date': eventDateController.text,
          'event_place': eventPlaceController.text,
          'event_location': '',
        }),
      );

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Event created successfully!')),
        );
        eventNameController.clear();
        eventDateController.clear();
        eventPlaceController.clear();
        setState(() {
          myEventsData = fetchMyEvents();
        });
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to create event')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final tabs = [
      '👤 Profile',
      '💰 Contributions',
      '💵 Receipts',
      '📊 Give & Take',
      '📅 Events',
      '📣 Manage Events',
      '🎤 Voice Query',
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Moi Sei Family Portal'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () {
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (context) => const LoginScreen()),
              );
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Scrollable Tab Bar
          Container(
            color: Theme.of(context).primaryColor,
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: List.generate(tabs.length, (index) {
                  return InkWell(
                    onTap: () {
                      setState(() {
                        currentTabIndex = index;
                      });
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                      decoration: BoxDecoration(
                        border: Border(
                          bottom: BorderSide(
                            color: currentTabIndex == index
                                ? Colors.white
                                : Colors.transparent,
                            width: 3,
                          ),
                        ),
                      ),
                      child: Text(
                        tabs[index],
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: currentTabIndex == index
                              ? FontWeight.bold
                              : FontWeight.normal,
                        ),
                      ),
                    ),
                  );
                }),
              ),
            ),
          ),
          // Tab Content
          Expanded(
            child: IndexedStack(
              index: currentTabIndex,
              children: [
                _buildProfileTab(),
                _buildContributionsTab(),
                _buildReceiptsTab(),
                _buildGiveAndTakeTab(),
                _buildUpcomingEventsTab(),
                _buildManageEventsTab(),
                _buildVoiceQueryTab(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProfileTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Family Profile',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 20),
                  _profileRow('Husband:', widget.family.husbandName),
                  _profileRow('Wife:', widget.family.wifeName ?? 'N/A'),
                  _profileRow('Phone:', widget.family.phoneNumber),
                  _profileRow('Place:', widget.family.place ?? 'N/A'),
                  _profileRow('Family ID:', widget.family.id.toString()),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _profileRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
          Text(value),
        ],
      ),
    );
  }

  Widget _buildUpcomingEventsTab() {
    return FutureBuilder<List<dynamic>>(
      future: upcomingEventsData,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError) {
          return Center(child: Text('Error: ${snapshot.error}'));
        }

        final events = snapshot.data ?? [];

        if (events.isEmpty) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Text('No upcoming events'),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () {
                    setState(() {
                      upcomingEventsData = fetchUpcomingEvents();
                    });
                  },
                  child: const Text('Refresh'),
                ),
              ],
            ),
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: events.length,
          itemBuilder: (context, index) {
            final event = events[index];
            return Card(
              child: ListTile(
                title: Text(event['event_name'] ?? 'Event'),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Family: ${event['other_husband_name'] ?? 'N/A'}'),
                    Text('Date: ${event['event_date'] ?? 'TBD'}'),
                  ],
                ),
                trailing: const Icon(Icons.calendar_today),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildContributionsTab() {
    return FutureBuilder<List<dynamic>>(
      future: contributionsData,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError) {
          return Center(child: Text('Error: ${snapshot.error}'));
        }

        final contributions = snapshot.data ?? [];

        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'My Contributions (What I Gave)',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              if (contributions.isEmpty)
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('No contributions yet'),
                  ),
                )
              else
                ...List.generate(contributions.length, (index) {
                  final c = contributions[index];
                  final amount = double.parse(c['amount']?.toString() ?? '0');
                  return Card(
                    margin: const EdgeInsets.only(bottom: 12),
                    child: ListTile(
                      leading: const Icon(Icons.arrow_upward, color: Colors.green),
                      title: Text(c['event_name'] ?? 'Event'),
                      subtitle: Text('To: ${c['receiver_name'] ?? 'Family'}'),
                      trailing: Text(
                        '+₹${amount.toStringAsFixed(2)}',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.green,
                        ),
                      ),
                    ),
                  );
                }),
            ],
          ),
        );
      },
    );
  }

  Widget _buildReceiptsTab() {
    return FutureBuilder<List<dynamic>>(
      future: receiptsData,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError) {
          return Center(child: Text('Error: ${snapshot.error}'));
        }

        final receipts = snapshot.data ?? [];

        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'My Receipts (What I Received)',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              if (receipts.isEmpty)
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('No receipts yet'),
                  ),
                )
              else
                ...List.generate(receipts.length, (index) {
                  final r = receipts[index];
                  final amount = double.parse(r['amount']?.toString() ?? '0');
                  return Card(
                    margin: const EdgeInsets.only(bottom: 12),
                    child: ListTile(
                      leading: const Icon(Icons.arrow_downward, color: Colors.orange),
                      title: Text(r['event_name'] ?? 'Event'),
                      subtitle: Text('From: ${r['contributor_name'] ?? 'Family'}'),
                      trailing: Text(
                        '-₹${amount.toStringAsFixed(2)}',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.orange,
                        ),
                      ),
                    ),
                  );
                }),
            ],
          ),
        );
      },
    );
  }

  Widget _buildManageEventsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'My Hosted Events',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 16),
          
          // Event Creation Form
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Schedule a New Event',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: eventNameController,
                    decoration: const InputDecoration(
                      labelText: 'Event Name',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: eventDateController,
                    decoration: const InputDecoration(
                      labelText: 'Date (YYYY-MM-DD)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: eventPlaceController,
                    decoration: const InputDecoration(
                      labelText: 'Place',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    onPressed: createEvent,
                    icon: const Icon(Icons.add),
                    label: const Text('Create Event'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          
          // Events List
          Text(
            'Upcoming Events',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 12),
          FutureBuilder<List<dynamic>>(
            future: myEventsData,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const CircularProgressIndicator();
              }

              final events = snapshot.data ?? [];
              if (events.isEmpty) {
                return const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('No events created yet'),
                  ),
                );
              }

              return Column(
                children: List.generate(events.length, (index) {
                  final e = events[index];
                  return Card(
                    margin: const EdgeInsets.only(bottom: 12),
                    child: ListTile(
                      leading: const Icon(Icons.event),
                      title: Text(e['event_name'] ?? 'Event'),
                      subtitle: Text('${e['event_date']}\n${e['event_place'] ?? 'Location TBD'}'),
                      trailing: const Icon(Icons.arrow_forward),
                    ),
                  );
                }),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildVoiceQueryTab() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.mic,
              size: 64,
              color: Theme.of(context).primaryColor,
            ),
            const SizedBox(height: 16),
            const Text('Voice Query Feature'),
            const SizedBox(height: 8),
            const Text(
              'Ask questions about your transactions by voice. Ask "Tell me my total contributions" or "Who do I owe money to?"',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Voice Query - Coming Soon in next update!')),
                );
              },
              icon: const Icon(Icons.mic),
              label: const Text('Start Voice Query'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildScheduleEventsTab() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.event_available,
              size: 64,
              color: Theme.of(context).primaryColor,
            ),
            const SizedBox(height: 16),
            const Text('Schedule & Manage Events'),
            const SizedBox(height: 8),
            const Text(
              'Event scheduling feature coming soon!',
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGiveAndTakeTab() {
    return FutureBuilder<Map<String, dynamic>>(
      future: transactionData,
      builder: (context, transSnapshot) {
        if (transSnapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (transSnapshot.hasError) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text('Error: ${transSnapshot.error}'),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () {
                    setState(() {
                      transactionData = fetchTransactions();
                    });
                  },
                  child: const Text('Retry'),
                ),
              ],
            ),
          );
        }

        if (!transSnapshot.hasData) {
          return const Center(child: Text('No data available'));
        }

        final transData = transSnapshot.data!;
        final summary = transData['summary'] as Map<String, dynamic>;
        final transactions = (transData['transactions'] as List? ?? [])
            .map((t) => t as Map<String, dynamic>)
            .toList();

        return FutureBuilder<List<dynamic>>(
          future: partnerHistoryData,
          builder: (context, partSnapshot) {
            if (partSnapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }

            if (partSnapshot.hasError) {
              return Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.error, size: 48, color: Colors.red),
                    const SizedBox(height: 16),
                    Text('Error loading partner history:\n${partSnapshot.error}',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: () {
                        setState(() {
                          partnerHistoryData = fetchPartnerHistory();
                        });
                      },
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              );
            }

            final partners = partSnapshot.data ?? [];

            return SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Overall Transaction Summary
                  Text(
                    'Overall Summary',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: Card(
                          color: Colors.green.shade50,
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('Total Given',
                                    style: Theme.of(context).textTheme.bodySmall),
                                const SizedBox(height: 8),
                                Text(
                                  '₹${summary['total_given']?.toStringAsFixed(2) ?? '0.00'}',
                                  style: Theme.of(context)
                                      .textTheme
                                      .headlineSmall
                                      ?.copyWith(color: Colors.green),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Card(
                          color: Colors.orange.shade50,
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('Total Received',
                                    style: Theme.of(context).textTheme.bodySmall),
                                const SizedBox(height: 8),
                                Text(
                                  '₹${summary['total_received']?.toStringAsFixed(2) ?? '0.00'}',
                                  style: Theme.of(context)
                                      .textTheme
                                      .headlineSmall
                                      ?.copyWith(color: Colors.orange),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Card(
                    color: summary['net_balance'] > 0
                        ? Colors.blue.shade50
                        : Colors.red.shade50,
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            summary['net_balance'] > 0
                                ? '📈 Net (You gave more)'
                                : '📉 Net (You received more)',
                            style: Theme.of(context).textTheme.bodyLarge,
                          ),
                          Text(
                            '₹${summary['net_balance']?.abs().toStringAsFixed(2) ?? '0.00'}',
                            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                              color: summary['net_balance'] > 0
                                  ? Colors.blue
                                  : Colors.red,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Transaction List
                  Text(
                    'Transaction History',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 12),
                  if (transactions.isEmpty)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(
                          'No transactions yet',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ),
                    )
                  else
                    ListView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: transactions.length,
                      itemBuilder: (context, index) {
                        final tx = transactions[index];
                        final isGiven = tx['type'] == 'given';
                        return Card(
                          child: ListTile(
                            leading: Icon(
                              isGiven
                                  ? Icons.arrow_upward
                                  : Icons.arrow_downward,
                              color: isGiven ? Colors.green : Colors.orange,
                            ),
                            title: Text(tx['event_name'] ?? 'Event'),
                            subtitle: Text(
                              '${tx['counterparty_name'] ?? 'Family'}\n${tx['transaction_date'] ?? ''}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            trailing: Text(
                              '${isGiven ? '+' : '-'}₹${double.parse(tx['amount'].toString()).toStringAsFixed(2)}',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: isGiven ? Colors.green : Colors.orange,
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  const SizedBox(height: 24),

                  // Partner Summary
                  Text(
                    'Give & Take Summary (All Events)',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'For each family you\'ve exchanged with: what you\'ve given, received, and the net difference.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 16),
                  if (partners.isEmpty)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(
                          'No shared history with other families yet',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ),
                    )
                  else
                    ...List.generate(partners.length, (index) {
                      final partner = partners[index];
                      final given = double.parse(partner['total_given']?.toString() ?? '0');
                      final received = double.parse(partner['total_received']?.toString() ?? '0');
                      final net = double.parse(partner['net_difference']?.toString() ?? '0');

                      return Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                partner['other_husband_name'] ?? 'Family',
                                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              Text(
                                '📞 ${partner['other_phone_number'] ?? 'N/A'}',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                              const SizedBox(height: 12),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'You Gave',
                                        style: Theme.of(context).textTheme.bodySmall,
                                      ),
                                      Text(
                                        '₹${given.toStringAsFixed(2)}',
                                        style: const TextStyle(
                                          fontSize: 16,
                                          fontWeight: FontWeight.bold,
                                          color: Colors.green,
                                        ),
                                      ),
                                    ],
                                  ),
                                  Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'You Received',
                                        style: Theme.of(context).textTheme.bodySmall,
                                      ),
                                      Text(
                                        '₹${received.toStringAsFixed(2)}',
                                        style: const TextStyle(
                                          fontSize: 16,
                                          fontWeight: FontWeight.bold,
                                          color: Colors.orange,
                                        ),
                                      ),
                                    ],
                                  ),
                                  Column(
                                    crossAxisAlignment: CrossAxisAlignment.end,
                                    children: [
                                      Text(
                                        'Net Balance',
                                        style: Theme.of(context).textTheme.bodySmall,
                                      ),
                                      Text(
                                        net > 0 ? '+₹${net.toStringAsFixed(2)}' : '-₹${(-net).toStringAsFixed(2)}',
                                        style: TextStyle(
                                          fontSize: 16,
                                          fontWeight: FontWeight.bold,
                                          color: net > 0 ? Colors.blue : Colors.red,
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      );
                    }),
                ],
              ),
            );
          },
        );
      },
    );
  }
}
