#!/usr/bin/env python3
"""
Vieweo - AI Visibility Platform for Real Estate Agents
Production-Ready Version with Modern UI
"""

import os
import sys
from flask import Flask, request, jsonify, session, render_template_string
from flask_session import Session
from agent_intelligence_v2 import AgentIntelligenceSystem

# Flask Setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours
Session(app)

# Configuration
class Config:
    EXCEL_PATH = os.environ.get('EXCEL_PATH', 'US_Real_Estate_Agents_Database.xlsx')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))

system = None
_system_loading = False

def get_system(force_reload=False):
    """Get or initialize the global system instance (thread-safe singleton)"""
    global system, _system_loading

    # Return existing system if already loaded
    if system is not None and not force_reload:
        return system

    # Prevent multiple simultaneous loads
    if _system_loading:
        import time
        # Wait for ongoing load to complete
        for _ in range(50):  # Wait up to 5 seconds
            time.sleep(0.1)
            if system is not None:
                return system
        raise RuntimeError("System initialization timeout")

    try:
        _system_loading = True

        # Find database file
        excel_path = Config.EXCEL_PATH
        for path in [Config.EXCEL_PATH, 'US_Real_Estate_Agents_Database.xlsx',
                     'US_Real_Estate_Agents_Database__2_.xlsx',
                     '/mnt/user-data/uploads/US_Real_Estate_Agents_Database__2_.xlsx',
                     'data/US_Real_Estate_Agents_Database.xlsx']:
            if os.path.exists(path):
                excel_path = path
                break

        print(f"\n{'='*60}")
        print(f"🚀 INITIALIZING VIEWEO SYSTEM")
        print(f"{'='*60}")
        system = AgentIntelligenceSystem(excel_path, Config.GEMINI_API_KEY)
        print(f"{'='*60}")
        print(f"✅ SYSTEM READY - {len(system.db.df)} agents loaded")
        print(f"{'='*60}\n")
        return system
    finally:
        _system_loading = False

# ============== API ROUTES ==============

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Simple login - store name/email in session

    Admin credentials for testing:
    - Email: admin@vieweo.com
    - Name: Admin (any first/last name)
    """
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()

    if not name or not email:
        return jsonify({'error': 'Name and email are required'}), 400

    # Check for admin credentials (full access to everything)
    is_admin = email.lower() == 'admin@vieweo.com'

    session['user'] = {
        'name': name,
        'email': email,
        'logged_in': True,
        'paid': is_admin,  # Admin gets full paid access
        'is_admin': is_admin
    }

    if is_admin:
        print(f"🔑 Admin login: {name}")
    else:
        print(f"👤 User login: {name} ({email})")

    return jsonify({'success': True, 'user': session['user']})

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check auth status"""
    return jsonify(session.get('user', {'logged_in': False, 'paid': False}))

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout user"""
    session.clear()
    return jsonify({'success': True})

@app.route('/api/auth/upgrade', methods=['POST'])
def upgrade():
    """Simulate payment upgrade"""
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    session['user']['paid'] = True
    session.modified = True
    return jsonify({'success': True, 'user': session['user']})

@app.route('/api/search', methods=['GET'])
def search_agents():
    """Search agents by name or location"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Query required'}), 400

    sys = get_system()
    results = sys.db.search(query)[:10]

    # Format results - ensure all fields are present
    formatted_results = []
    for r in results:
        formatted_results.append({
            'id': r.get('id', ''),
            'name': r.get('name', ''),
            'city': r.get('city', ''),
            'state': r.get('state', '')
        })

    return jsonify({
        'count': len(formatted_results),
        'results': formatted_results
    })

@app.route('/api/visibility/free', methods=['GET'])
def free_visibility():
    """Basic agent details - no login required. SALT scores require login."""
    name = request.args.get('name', '').strip()
    print(f"\n🔍 Visibility request for: '{name}'")

    if not name:
        return jsonify({'error': 'Agent name required'}), 400

    # Check session cache first - ALWAYS use cache if available
    cache_key = f"agent_data_{name.lower()}"
    if cache_key in session:
        print(f"✅ Using cached data for: {name}")
        cached_data = session[cache_key]
        # Update user status dynamically
        user = session.get('user', {})
        cached_data['user_status'] = {
            'logged_in': bool(user),
            'is_admin': user.get('is_admin', False),
            'paid': user.get('paid', False)
        }
        return jsonify(cached_data)

    try:
        sys = get_system()
        result = sys.analyze_agent(name)
        print(f"✅ Analysis complete for: {name}")
    except Exception as e:
        print(f"❌ Error analyzing agent: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

    if 'error' in result:
        print(f"❌ Agent not found: {name}")
        return jsonify({'error': result['error'], 'not_found': True}), 404

    # Extract data
    agent = result['agent']
    analysis = result['analysis']
    lb = result.get('leaderboard_context', {})

    # Safe score access
    overall_score = analysis.get('scores', {}).get('overall', {}).get('score', 0) or 0
    authority_score = analysis.get('scores', {}).get('authority', {}).get('score', 0) or 0
    semantic_score = analysis.get('scores', {}).get('semantic', {}).get('score', 0) or 0
    location_score = analysis.get('scores', {}).get('location', {}).get('score', 0) or 0
    trust_score = analysis.get('scores', {}).get('trust', {}).get('score', 0) or 0

    # Get user status
    user = session.get('user', {})
    is_logged_in = bool(user)
    is_admin = user.get('is_admin', False)

    # Build response with tiered access
    response_data = {
        # TIER 1: Always visible (no login required)
        'agent': {
            'name': agent.get('name', ''),
            'city': agent.get('location', {}).get('city', ''),
            'state': agent.get('location', {}).get('state', ''),
            'brokerage': agent.get('brokerage', ''),
            'years_experience': agent.get('experience', {}).get('years', 0),
            'phone': agent.get('phone', ''),
            'email': agent.get('email', ''),
            'website': agent.get('online_presence', {}).get('website', ''),
        },
        'basic_metrics': {
            'average_rating': agent.get('reviews', {}).get('average_rating', 0),
            'total_reviews': agent.get('reviews', {}).get('total_count', 0),
            'specialization': agent.get('experience', {}).get('specialization', ''),
        },
        'visibility_score': overall_score,
        'visibility_grade': analysis.get('scores', {}).get('overall', {}).get('grade', 'N/A'),
        'visibility_tier': analysis.get('scores', {}).get('overall', {}).get('tier', 'Unknown'),

        # TIER 2: Requires login (SALT scores)
        'salt_scores': {
            'semantic': semantic_score,
            'authority': authority_score,
            'location': location_score,
            'trust': trust_score
        } if is_logged_in or is_admin else None,

        'ranking_preview': {
            'state_rank': lb.get('state_rank', '?'),
            'state_total': lb.get('state_total', '?'),
            'state': agent.get('location', {}).get('state', 'Unknown')
        } if is_logged_in or is_admin else None,

        # User status
        'user_status': {
            'logged_in': is_logged_in,
            'is_admin': is_admin,
            'paid': user.get('paid', False)
        },

        'requires_login_for': ['salt_scores', 'ranking_preview'] if not is_logged_in else [],
        'requires_payment_for': ['full_report', 'competitors', 'action_plan']
    }

    # Cache in session
    session[cache_key] = response_data
    session.modified = True

    print(f"✅ Cached and returning data: score={overall_score}")
    return jsonify(response_data)

@app.route('/api/visibility/full', methods=['GET'])
def full_visibility():
    """Full visibility report - requires payment"""
    user = session.get('user', {})
    if not user.get('paid'):
        return jsonify({'error': 'Payment required', 'upgrade_required': True}), 403

    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Agent name required'}), 400

    # Check session cache first
    cache_key = f"full_report_{name.lower()}"
    if cache_key in session:
        print(f"✅ Using cached full report for: {name}")
        return jsonify(session[cache_key])

    sys = get_system()
    result = sys.analyze_agent(name)

    if 'error' in result:
        return jsonify(result), 404

    # Cache the full report
    session[cache_key] = result
    session.modified = True
    print(f"✅ Cached full report for: {name}")

    return jsonify(result)

@app.route('/api/agents/add', methods=['POST'])
def add_agent():
    """Add a new agent to the database"""
    data = request.get_json() or {}

    # Validate required fields
    required_fields = ['full_name', 'city', 'state', 'phone']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    try:
        import pandas as pd

        # Generate unique Agent_ID
        sys = get_system()
        max_id = sys.db.df['Agent_ID'].astype(str).str.extract('(\d+)').astype(int).max()[0]
        new_id = f"AG{max_id + 1:06d}"

        # Prepare new agent row
        new_agent = {
            'Agent_ID': new_id,
            'Full_Name': data['full_name'],
            'City': data['city'],
            'State': data['state'],
            'Phone': data['phone'],
            'Email': data.get('email', ''),
            'Brokerage_Name': data.get('brokerage', ''),
            'Website': data.get('website', ''),
            'Years_Experience': data.get('years_experience', 0),
            'Specialization': data.get('specialization', ''),
            'Average_Rating': 0,
            'Total_Reviews': 0,
            'Credibility_Score': 0
        }

        # Add to DataFrame
        sys.db.df = pd.concat([sys.db.df, pd.DataFrame([new_agent])], ignore_index=True)

        # Save to Excel
        excel_path = Config.EXCEL_PATH
        sys.db.df.to_excel(excel_path, index=False)

        # Rebuild search cache
        sys.db._build_search_cache()

        print(f"✅ Added new agent: {new_agent['Full_Name']} (ID: {new_id})")

        return jsonify({
            'success': True,
            'agent_id': new_id,
            'agent_name': new_agent['Full_Name'],
            'message': f'Agent added successfully! You can now search for {new_agent["Full_Name"]}.'
        })

    except Exception as e:
        print(f"❌ Error adding agent: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to add agent: {str(e)}'}), 500

# ============== FRONTEND ==============

@app.route('/')
def index():
    return render_template_string(FRONTEND_HTML)

FRONTEND_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vieweo - AI Visibility Platform for Real Estate Agents</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        * {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideIn { from { transform: translateX(-100%); } to { transform: translateX(0); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .animate-in { animation: fadeIn 0.5s ease-out forwards; }
        .animate-slide { animation: slideIn 0.4s ease-out forwards; }
        .gradient-text {
            background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .glass-effect {
            background: rgba(255, 255, 255, 0.8);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
        }
    </style>
</head>
<body class="bg-gradient-to-br from-gray-50 to-gray-100">
    <div id="root"></div>

    <script type="text/babel">
        const { useState, useEffect, useRef } = React;

        // ============== LOADING COMPONENT ==============
        const LoadingScreen = ({ title = "Analyzing", subtitle = "AI processing in progress" }) => {
            const [dots, setDots] = useState('');
            const [stepIndex, setStepIndex] = useState(0);

            const steps = [
                "Searching database",
                "Loading agent profile",
                "Calculating visibility scores",
                "Analyzing market position",
                "Computing SALT metrics",
                "Generating insights",
                "Finalizing analysis"
            ];

            useEffect(() => {
                const dotsTimer = setInterval(() => {
                    setDots(prev => prev.length >= 3 ? '' : prev + '.');
                }, 400);

                const stepTimer = setInterval(() => {
                    setStepIndex(prev => (prev + 1) % steps.length);
                }, 1800);

                return () => {
                    clearInterval(dotsTimer);
                    clearInterval(stepTimer);
                };
            }, []);

            return (
                <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950 flex items-center justify-center p-6 relative overflow-hidden">
                    {/* Animated background */}
                    <div className="absolute inset-0 overflow-hidden">
                        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" style={{animationDuration: '4s'}}/>
                        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse" style={{animationDuration: '6s', animationDelay: '1s'}}/>
                    </div>

                    <div className="relative z-10 text-center max-w-2xl w-full">
                        {/* Dual spinner */}
                        <div className="mb-8 relative">
                            <div className="w-24 h-24 mx-auto relative">
                                <div className="absolute inset-0 border-4 border-blue-500/20 rounded-full"/>
                                <div className="absolute inset-0 border-4 border-transparent border-t-blue-500 rounded-full animate-spin" style={{animationDuration: '1s'}}/>
                                <div className="absolute inset-2 border-4 border-transparent border-t-purple-400 rounded-full animate-spin" style={{animationDuration: '1.5s', animationDirection: 'reverse'}}/>
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <div className="w-3 h-3 bg-blue-400 rounded-full animate-pulse"/>
                                </div>
                            </div>
                        </div>

                        <h2 className="text-3xl font-bold text-white mb-3">{title}{dots}</h2>
                        <p className="text-blue-200/60 text-lg mb-8">{subtitle}</p>

                        {/* Progress steps */}
                        <div className="bg-slate-900/40 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-6 shadow-2xl">
                            <div className="space-y-3">
                                {steps.map((step, idx) => {
                                    const isPast = idx < stepIndex;
                                    const isCurrent = idx === stepIndex;
                                    return (
                                        <div key={idx} className="flex items-center gap-3 transition-all duration-500">
                                            <div className={`w-6 h-6 rounded-full flex items-center justify-center transition-all duration-500 ${
                                                isPast ? 'bg-green-500/20 border-2 border-green-500' :
                                                isCurrent ? 'bg-blue-500/20 border-2 border-blue-500 animate-pulse' :
                                                'bg-slate-700/20 border-2 border-slate-600'
                                            }`}>
                                                {isPast && <svg className="w-3 h-3 text-green-400" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/></svg>}
                                                {isCurrent && <div className="w-2 h-2 bg-blue-400 rounded-full animate-ping"/>}
                                            </div>
                                            <span className={`text-sm transition-all duration-500 ${
                                                isPast ? 'text-green-400/60' :
                                                isCurrent ? 'text-blue-300 font-medium' :
                                                'text-slate-500'
                                            }`}>
                                                {step}{isCurrent ? dots : ''}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        <p className="text-slate-500 text-xs mt-6 animate-pulse">Powered by Gemini AI</p>
                    </div>
                </div>
            );
        };

        // ============== LOGIN MODAL ==============
        const LoginModal = ({ show, onClose, onSuccess }) => {
            const [loading, setLoading] = useState(false);
            const [error, setError] = useState('');

            if (!show) return null;

            const handleSubmit = async (e) => {
                e.preventDefault();
                setLoading(true);
                setError('');

                const formData = new FormData(e.target);
                const firstName = formData.get('first_name');
                const lastName = formData.get('last_name');
                const email = formData.get('email');

                try {
                    const r = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: `${firstName} ${lastName}`, email })
                    });

                    const d = await r.json();

                    if (d.success) {
                        onSuccess(d.user);
                        onClose();
                    } else {
                        setError(d.error || 'Login failed');
                    }
                } catch (err) {
                    setError('Network error. Please try again.');
                } finally {
                    setLoading(false);
                }
            };

            return (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in">
                    <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-8 relative animate-in">
                        <button
                            onClick={onClose}
                            className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100 transition"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
                            </svg>
                        </button>

                        <div className="text-center mb-6">
                            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                                <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                                </svg>
                            </div>
                            <h3 className="text-2xl font-bold text-gray-900 mb-1">Welcome to Vieweo</h3>
                            <p className="text-sm text-gray-500">Access SALT scores and detailed insights</p>
                        </div>

                        {error && (
                            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                                {error}
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-semibold text-gray-700 mb-1">First Name</label>
                                    <input
                                        name="first_name"
                                        type="text"
                                        required
                                        className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                        placeholder="John"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-gray-700 mb-1">Last Name</label>
                                    <input
                                        name="last_name"
                                        type="text"
                                        required
                                        className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                        placeholder="Smith"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-semibold text-gray-700 mb-1">Email</label>
                                <input
                                    name="email"
                                    type="email"
                                    required
                                    className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                    placeholder="john@example.com"
                                />
                            </div>
                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-xl hover:from-blue-700 hover:to-purple-700 transition shadow-lg shadow-blue-500/30 disabled:opacity-50"
                            >
                                {loading ? 'Signing In...' : 'Sign In'}
                            </button>
                        </form>

                        <p className="text-xs text-gray-500 text-center mt-4">
                            Test with admin@vieweo.com for full access
                        </p>
                    </div>
                </div>
            );
        };

        // ============== ADD AGENT MODAL ==============
        const AddAgentModal = ({ show, onClose, onSuccess }) => {
            const [loading, setLoading] = useState(false);
            const [error, setError] = useState('');

            if (!show) return null;

            const handleSubmit = async (e) => {
                e.preventDefault();
                setLoading(true);
                setError('');

                const formData = new FormData(e.target);
                const data = {
                    full_name: formData.get('full_name'),
                    city: formData.get('city'),
                    state: formData.get('state'),
                    phone: formData.get('phone'),
                    email: formData.get('email'),
                    brokerage: formData.get('brokerage'),
                    website: formData.get('website'),
                    years_experience: parseInt(formData.get('years_experience')) || 0,
                    specialization: formData.get('specialization')
                };

                try {
                    const r = await fetch('/api/agents/add', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });

                    const result = await r.json();

                    if (result.success) {
                        onSuccess(result);
                        onClose();
                    } else {
                        setError(result.error || 'Failed to add agent');
                    }
                } catch (err) {
                    setError('Network error. Please try again.');
                } finally {
                    setLoading(false);
                }
            };

            return (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
                    <div className="bg-white rounded-3xl shadow-2xl max-w-2xl w-full p-8 my-8 relative animate-in">
                        <button
                            onClick={onClose}
                            className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100 transition"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/>
                            </svg>
                        </button>

                        <div className="text-center mb-6">
                            <div className="w-16 h-16 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                                <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
                                </svg>
                            </div>
                            <h3 className="text-2xl font-bold text-gray-900 mb-1">Add New Agent</h3>
                            <p className="text-sm text-gray-500">Register a new agent to access GEO scores</p>
                        </div>

                        {error && (
                            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                                {error}
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="block text-xs font-semibold text-gray-700 mb-1">Full Name *</label>
                                <input name="full_name" type="text" required className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition" placeholder="John Smith"/>
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-semibold text-gray-700 mb-1">City *</label>
                                    <input name="city" type="text" required className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition" placeholder="Los Angeles"/>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-gray-700 mb-1">State *</label>
                                    <input name="state" type="text" required className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition" placeholder="CA"/>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-semibold text-gray-700 mb-1">Phone *</label>
                                    <input name="phone" type="tel" required className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition" placeholder="(555) 123-4567"/>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-gray-700 mb-1">Email</label>
                                    <input name="email" type="email" className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition" placeholder="john@example.com"/>
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-gray-700 mb-1">Brokerage</label>
                                <input name="brokerage" type="text" className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition" placeholder="Coldwell Banker"/>
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-semibold text-gray-700 mb-1">Years of Experience</label>
                                    <input name="years_experience" type="number" min="0" className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition" placeholder="5"/>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-gray-700 mb-1">Specialization</label>
                                    <input name="specialization" type="text" className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition" placeholder="Luxury Homes"/>
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-gray-700 mb-1">Website</label>
                                <input name="website" type="url" className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition" placeholder="https://www.example.com"/>
                            </div>

                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full py-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-semibold rounded-xl hover:from-emerald-700 hover:to-teal-700 transition shadow-lg shadow-emerald-500/30 disabled:opacity-50"
                            >
                                {loading ? 'Adding Agent...' : 'Add Agent'}
                            </button>
                        </form>
                    </div>
                </div>
            );
        };

        // ============== NAVBAR ==============
        const Navbar = ({ user, onLogin, onLogout, onAddAgent }) => (
            <nav className="glass-effect border-b border-gray-200/50 sticky top-0 z-40 shadow-sm">
                <div className="max-w-7xl mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl flex items-center justify-center">
                                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                                </svg>
                            </div>
                            <h1 className="text-2xl font-bold gradient-text">Vieweo</h1>
                        </div>

                        <div className="flex items-center gap-3">
                            <button
                                onClick={onAddAgent}
                                className="px-4 py-2 text-sm font-medium text-emerald-700 bg-emerald-50 rounded-lg hover:bg-emerald-100 transition flex items-center gap-2"
                            >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4"/>
                                </svg>
                                Add Agent
                            </button>

                            {user ? (
                                <div className="flex items-center gap-3">
                                    {user.is_admin && (
                                        <span className="px-3 py-1 bg-purple-100 text-purple-700 text-xs font-bold rounded-full">
                                            ADMIN
                                        </span>
                                    )}
                                    <span className="text-sm text-gray-700 font-medium">{user.name}</span>
                                    <button
                                        onClick={onLogout}
                                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition"
                                    >
                                        Logout
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={onLogin}
                                    className="px-6 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-lg hover:from-blue-700 hover:to-purple-700 transition shadow-lg shadow-blue-500/30"
                                >
                                    Sign In
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            </nav>
        );

        // ============== SEARCH PAGE ==============
        const SearchPage = ({ user, onSearch, onLogin, onLogout, onAddAgent }) => {
            const [query, setQuery] = useState('');
            const [suggestions, setSuggestions] = useState([]);
            const [loading, setLoading] = useState(false);

            useEffect(() => {
                if (query.length >= 2) {
                    setLoading(true);
                    const timer = setTimeout(() => {
                        fetch(`/api/search?q=${encodeURIComponent(query)}`)
                            .then(r => r.json())
                            .then(d => {
                                setSuggestions(d.results || []);
                                setLoading(false);
                            })
                            .catch(() => {
                                setSuggestions([]);
                                setLoading(false);
                            });
                    }, 150);
                    return () => clearTimeout(timer);
                } else {
                    setSuggestions([]);
                    setLoading(false);
                }
            }, [query]);

            return (
                <div className="min-h-screen">
                    <Navbar user={user} onLogin={onLogin} onLogout={onLogout} onAddAgent={onAddAgent} />

                    {/* Hero Section */}
                    <div className="relative bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 overflow-hidden">
                        <img
                            src="https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1600"
                            alt=""
                            className="absolute inset-0 w-full h-full object-cover opacity-20"
                        />

                        <div className="relative z-10 max-w-5xl mx-auto px-6 py-24 text-center">
                            <h2 className="text-5xl font-extrabold text-white mb-4 leading-tight">
                                Be the Agent <span className="text-blue-400">AI Recommends</span>
                            </h2>
                            <p className="text-xl text-blue-100 mb-12 max-w-3xl mx-auto">
                                Measure and optimize your visibility on AI platforms like ChatGPT, Claude, and Perplexity.
                                Dominate your market with AI-powered insights.
                            </p>

                            {/* Search Box */}
                            <div className="max-w-2xl mx-auto relative">
                                <div className="flex items-center glass-effect rounded-2xl shadow-2xl overflow-hidden border border-white/20">
                                    <div className="pl-6 text-gray-400">
                                        {loading ? (
                                            <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"/>
                                        ) : (
                                            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                                            </svg>
                                        )}
                                    </div>
                                    <input
                                        type="text"
                                        value={query}
                                        onChange={e => setQuery(e.target.value)}
                                        onKeyDown={e => {
                                            if (e.key === 'Enter' && query) {
                                                onSearch(query);
                                            }
                                        }}
                                        placeholder="Search by agent name, city, or state..."
                                        className="flex-1 px-4 py-5 text-lg bg-transparent focus:outline-none text-gray-900 placeholder-gray-500"
                                    />
                                    <button
                                        onClick={() => query && onSearch(query)}
                                        className="m-2 px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-bold rounded-xl hover:from-blue-700 hover:to-purple-700 transition shadow-lg"
                                    >
                                        Check Visibility
                                    </button>
                                </div>

                                {/* Suggestions Dropdown */}
                                {suggestions.length > 0 && (
                                    <div className="absolute top-full left-0 right-0 mt-2 glass-effect rounded-2xl shadow-2xl border border-gray-200/50 overflow-hidden z-20 max-h-96 overflow-y-auto">
                                        {suggestions.map(s => (
                                            <button
                                                key={s.id}
                                                onClick={() => onSearch(s.name)}
                                                className="w-full px-6 py-4 text-left hover:bg-white/50 flex items-center gap-4 border-b border-gray-200/30 last:border-0 transition"
                                            >
                                                <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 text-white rounded-xl flex items-center justify-center font-bold text-lg">
                                                    {s.name ? s.name[0] : '?'}
                                                </div>
                                                <div>
                                                    <div className="font-semibold text-gray-900">{s.name}</div>
                                                    <div className="text-sm text-gray-600">{s.city}, {s.state}</div>
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Features Section */}
                    <div className="max-w-6xl mx-auto px-6 py-20">
                        <div className="grid md:grid-cols-3 gap-8">
                            {[
                                { icon: '🎯', title: 'SALT Score', desc: 'Semantic, Authority, Location, Trust metrics' },
                                { icon: '📊', title: 'Market Insights', desc: 'Compare against local competitors' },
                                { icon: '🚀', title: 'Action Plan', desc: 'Get personalized recommendations' }
                            ].map((f, i) => (
                                <div key={i} className="bg-white rounded-2xl p-8 border border-gray-200 hover:shadow-xl transition animate-in" style={{animationDelay: `${i * 100}ms`}}>
                                    <div className="text-5xl mb-4">{f.icon}</div>
                                    <h3 className="text-xl font-bold text-gray-900 mb-2">{f.title}</h3>
                                    <p className="text-gray-600">{f.desc}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            );
        };

        // ============== SNAPSHOT PAGE ==============
        const SnapshotPage = ({ agentName, user, onBack, onUpgrade, onLogin, onLogout, onAddAgent }) => {
            const [data, setData] = useState(null);
            const [loading, setLoading] = useState(true);
            const [showLoginModal, setShowLoginModal] = useState(false);

            useEffect(() => {
                setLoading(true);
                fetch(`/api/visibility/free?name=${encodeURIComponent(agentName)}`)
                    .then(r => r.json())
                    .then(d => {
                        setData(d);
                        setLoading(false);
                    })
                    .catch(() => {
                        setData({error: 'Failed to load data'});
                        setLoading(false);
                    });
            }, [agentName, user]);

            if (loading) return <LoadingScreen title="Analyzing Visibility" subtitle="Computing AI discoverability metrics"/>;

            if (!data || data.error) {
                const isNotFound = data?.not_found;
                return (
                    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 p-6">
                        <div className="max-w-md w-full bg-white rounded-3xl shadow-xl border border-gray-100 p-8 text-center">
                            <div className="w-20 h-20 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-6">
                                <svg className="w-10 h-10 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                                </svg>
                            </div>
                            <h2 className="text-2xl font-bold text-gray-900 mb-3">
                                {isNotFound ? 'Agent Not Found' : 'Error Loading Data'}
                            </h2>
                            <p className="text-gray-600 mb-6">
                                {isNotFound
                                    ? `We couldn't find "${agentName}" in our database. Would you like to add them?`
                                    : data?.error || 'Something went wrong. Please try again.'
                                }
                            </p>
                            <div className="space-y-3">
                                {isNotFound && (
                                    <button
                                        onClick={onAddAgent}
                                        className="w-full px-6 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-semibold rounded-xl hover:from-emerald-700 hover:to-teal-700 transition shadow-lg"
                                    >
                                        Add This Agent
                                    </button>
                                )}
                                <button
                                    onClick={onBack}
                                    className="w-full px-6 py-3 bg-gray-100 text-gray-700 font-semibold rounded-xl hover:bg-gray-200 transition"
                                >
                                    Back to Search
                                </button>
                            </div>
                        </div>
                    </div>
                );
            }

            const isLoggedIn = data.user_status?.logged_in;
            const isPaid = data.user_status?.paid;

            // Score ring color
            const scoreColor = data.visibility_score >= 80 ? 'from-emerald-500 to-green-600' :
                              data.visibility_score >= 60 ? 'from-amber-500 to-orange-600' :
                              'from-red-500 to-rose-600';

            return (
                <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
                    <Navbar user={user} onLogin={() => setShowLoginModal(true)} onLogout={onLogout} onAddAgent={onAddAgent} />

                    <div className="max-w-6xl mx-auto px-6 py-8">
                        {/* Back button */}
                        <button
                            onClick={onBack}
                            className="mb-6 text-gray-600 hover:text-gray-900 flex items-center gap-2 transition"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
                            </svg>
                            Back to Search
                        </button>

                        {/* Agent Header Card */}
                        <div className="bg-white rounded-3xl p-8 shadow-xl border border-gray-200 mb-6 animate-in">
                            <div className="flex flex-col lg:flex-row items-center gap-8">
                                {/* Avatar */}
                                <div className={`w-32 h-32 bg-gradient-to-br ${scoreColor} rounded-3xl flex items-center justify-center text-white text-4xl font-bold shadow-lg`}>
                                    {(data.agent.name || 'NA').split(' ').map(n => n[0]).join('')}
                                </div>

                                {/* Info */}
                                <div className="flex-1 text-center lg:text-left">
                                    <h1 className="text-4xl font-extrabold text-gray-900 mb-2">{data.agent.name}</h1>
                                    <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4 text-gray-600 mb-3">
                                        <span className="flex items-center gap-2">
                                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                                            </svg>
                                            {data.agent.brokerage || 'Independent'}
                                        </span>
                                        <span className="flex items-center gap-2">
                                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                                            </svg>
                                            {data.agent.city}, {data.agent.state}
                                        </span>
                                    </div>
                                    <div className="flex flex-wrap items-center justify-center lg:justify-start gap-3">
                                        <span className="px-4 py-2 bg-blue-50 text-blue-700 rounded-xl text-sm font-semibold">
                                            {data.agent.years_experience || 0}+ Years Experience
                                        </span>
                                        {data.basic_metrics.average_rating > 0 && (
                                            <span className="px-4 py-2 bg-amber-50 text-amber-700 rounded-xl text-sm font-semibold flex items-center gap-2">
                                                ⭐ {data.basic_metrics.average_rating.toFixed(1)} ({data.basic_metrics.total_reviews} reviews)
                                            </span>
                                        )}
                                    </div>
                                </div>

                                {/* Visibility Score */}
                                <div className="text-center">
                                    <div className={`w-40 h-40 rounded-3xl bg-gradient-to-br ${scoreColor} flex flex-col items-center justify-center text-white shadow-2xl`}>
                                        <div className="text-6xl font-extrabold">{data.visibility_score}</div>
                                        <div className="text-sm font-medium opacity-90">Visibility Score</div>
                                    </div>
                                    <div className="mt-3 px-4 py-2 bg-gray-100 rounded-xl text-sm font-semibold text-gray-700">
                                        {data.visibility_tier} Tier
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* SALT Scores Section */}
                        {isLoggedIn && data.salt_scores ? (
                            <div className="bg-white rounded-3xl p-8 shadow-xl border border-gray-200 mb-6 animate-in">
                                <h2 className="text-2xl font-bold text-gray-900 mb-6">SALT Score Breakdown</h2>
                                <div className="grid md:grid-cols-2 gap-6">
                                    {[
                                        { label: 'Semantic', score: data.salt_scores.semantic, icon: '🔍', color: 'blue' },
                                        { label: 'Authority', score: data.salt_scores.authority, icon: '👑', color: 'purple' },
                                        { label: 'Location', score: data.salt_scores.location, icon: '📍', color: 'green' },
                                        { label: 'Trust', score: data.salt_scores.trust, icon: '🛡️', color: 'amber' }
                                    ].map((metric, i) => (
                                        <div key={i} className="bg-gray-50 rounded-2xl p-6">
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="flex items-center gap-3">
                                                    <span className="text-3xl">{metric.icon}</span>
                                                    <span className="font-bold text-gray-900">{metric.label}</span>
                                                </div>
                                                <span className="text-2xl font-bold text-gray-900">{metric.score}</span>
                                            </div>
                                            <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full bg-gradient-to-r from-${metric.color}-500 to-${metric.color}-600 rounded-full transition-all duration-1000`}
                                                    style={{width: `${metric.score}%`}}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {data.ranking_preview && (
                                    # <div className="mt-6 p-6 bg-gradient-to-br from-blue-50 to-purple-50 rounded-2xl border border-blue-200">
                                    #     <p className="text-center text-lg font-semibold text-gray-900">
                                    #         Ranked <span className="text-blue-600 font-bold">#{data.ranking_preview.state_rank}</span> of {data.ranking_preview.state_total} agents in {data.ranking_preview.state}
                                    #     </p>
                                    # </div>
                                )}
                            </div>
                        ) : (
                            <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-12 text-center text-white mb-6 relative overflow-hidden animate-in">
                                <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMC41IiBvcGFjaXR5PSIwLjEiLz48L3BhdHRlcm4+PC9kZWZzPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9InVybCgjZ3JpZCkiLz48L3N2Zz4=')] opacity-30"/>
                                <div className="relative z-10">
                                    <div className="w-20 h-20 bg-white/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
                                        <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                                            <path d="M7 11V7a5 5 0 0110 0v4"/>
                                        </svg>
                                    </div>
                                    <h2 className="text-3xl font-bold mb-3">SALT Score Breakdown Locked</h2>
                                    <p className="text-blue-200 mb-8 max-w-2xl mx-auto">
                                        Sign in to view detailed SALT metrics (Semantic, Authority, Location, Trust) and see how you rank against local competitors.
                                    </p>
                                    <button
                                        onClick={() => setShowLoginModal(true)}
                                        className="px-8 py-4 bg-white text-gray-900 font-bold rounded-xl hover:bg-gray-100 transition shadow-2xl"
                                    >
                                        Sign In to Unlock
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Full Report CTA */}
                        <div className="bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 rounded-3xl p-12 text-center text-white shadow-2xl animate-in">
                            <h2 className="text-4xl font-extrabold mb-4">Unlock Full Visibility Report</h2>
                            <p className="text-xl text-blue-100 mb-8 max-w-3xl mx-auto">
                                Get comprehensive AI visibility analysis, competitor insights, market positioning, and personalized action plan to dominate your market.
                            </p>
                            <div className="flex flex-wrap items-center justify-center gap-6 mb-8">
                                {['📊 Full Analytics', '🎯 Competitor Analysis', '🚀 Action Plan', '📈 Market Trends'].map((f, i) => (
                                    <div key={i} className="flex items-center gap-2 text-sm font-medium bg-white/20 px-4 py-2 rounded-xl">
                                        {f}
                                    </div>
                                ))}
                            </div>
                            <button
                                onClick={onUpgrade}
                                className="px-12 py-5 bg-white text-blue-600 font-extrabold rounded-2xl hover:bg-gray-100 transition shadow-2xl text-xl"
                            >
                                {isPaid ? 'View Full Report' : 'Unlock Now - $49'}
                            </button>
                            {!isPaid && <p className="text-sm text-blue-100 mt-4">One-time payment • Instant access</p>}
                        </div>
                    </div>

                    <LoginModal
                        show={showLoginModal}
                        onClose={() => setShowLoginModal(false)}
                        onSuccess={(userData) => {
                            setShowLoginModal(false);
                            window.location.reload();
                        }}
                    />
                </div>
            );
        };

        // ============== PAYWALL PAGE ==============
        const PaywallPage = ({ agentName, user, onBack, onPaymentSuccess, onLogout, onAddAgent }) => {
            const [processing, setProcessing] = useState(false);

            const handlePayment = async () => {
                setProcessing(true);
                await new Promise(r => setTimeout(r, 1500));

                try {
                    const r = await fetch('/api/auth/upgrade', { method: 'POST' });
                    const d = await r.json();
                    if (d.success) {
                        onPaymentSuccess(d.user);
                    }
                } catch {
                    alert('Payment failed');
                } finally {
                    setProcessing(false);
                }
            };

            return (
                <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
                    <Navbar user={user} onLogin={() => {}} onLogout={onLogout} onAddAgent={onAddAgent} />

                    <div className="max-w-4xl mx-auto px-6 py-16">
                        <div className="bg-white rounded-3xl shadow-2xl border border-gray-200 overflow-hidden">
                            {/* Header */}
                            <div className="bg-gradient-to-br from-blue-600 to-purple-600 p-12 text-center text-white">
                                <h1 className="text-4xl font-extrabold mb-4">Unlock Your Full Visibility Report</h1>
                                <p className="text-xl text-blue-100">Get complete AI visibility analysis for {agentName}</p>
                            </div>

                            {/* Features */}
                            <div className="p-12">
                                <div className="grid md:grid-cols-2 gap-6 mb-10">
                                    {[
                                        { icon: '📊', title: 'Full Analytics Dashboard', desc: 'Comprehensive visibility metrics and trends' },
                                        { icon: '🎯', title: 'Competitor Analysis', desc: 'See how you stack up against local agents' },
                                        { icon: '🚀', title: 'Personalized Action Plan', desc: 'Step-by-step recommendations to improve' },
                                        { icon: '📈', title: 'Market Positioning', desc: 'Understand your position in the market' }
                                    ].map((f, i) => (
                                        <div key={i} className="flex items-start gap-4 p-6 bg-gray-50 rounded-2xl">
                                            <span className="text-4xl">{f.icon}</span>
                                            <div>
                                                <h3 className="font-bold text-gray-900 mb-1">{f.title}</h3>
                                                <p className="text-sm text-gray-600">{f.desc}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {/* Pricing */}
                                <div className="text-center p-8 bg-gradient-to-br from-blue-50 to-purple-50 rounded-2xl mb-8">
                                    <div className="text-6xl font-extrabold text-gray-900 mb-2">$49</div>
                                    <div className="text-gray-600 mb-6">One-time payment • Instant access • No subscription</div>
                                    <button
                                        onClick={handlePayment}
                                        disabled={processing}
                                        className="px-12 py-5 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-extrabold rounded-2xl hover:from-blue-700 hover:to-purple-700 transition shadow-2xl disabled:opacity-50 text-xl"
                                    >
                                        {processing ? 'Processing...' : 'Unlock Full Report Now'}
                                    </button>
                                </div>

                                <div className="text-center">
                                    <button
                                        onClick={onBack}
                                        className="text-gray-600 hover:text-gray-900 text-sm font-medium"
                                    >
                                        ← Back to Preview
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            );
        };

        // ============== FULL REPORT PAGE ==============
        const FullReportPage = ({ agentName, user, onBack, onLogout, onAddAgent }) => {
            const [data, setData] = useState(null);
            const [loading, setLoading] = useState(true);
            const [error, setError] = useState(null);

            useEffect(() => {
                setLoading(true);
                setError(null);
                fetch(`/api/visibility/full?name=${encodeURIComponent(agentName)}`)
                    .then(r => {
                        if (!r.ok) throw new Error(`HTTP ${r.status}`);
                        return r.json();
                    })
                    .then(d => {
                        if (d.error) {
                            setError(d.error);
                        } else {
                            setData(d);
                        }
                        setLoading(false);
                    })
                    .catch(e => {
                        setError(e.message);
                        setLoading(false);
                    });
            }, [agentName]);

            if (loading) return <LoadingScreen title="Generating Full Report" subtitle="Comprehensive AI visibility analysis"/>;

            if (error || !data) {
                return (
                    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 p-6">
                        <div className="max-w-md w-full bg-white rounded-3xl shadow-xl p-8 text-center">
                            <div className="w-20 h-20 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-6">
                                <svg className="w-10 h-10 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                                </svg>
                            </div>
                            <h2 className="text-2xl font-bold text-gray-900 mb-3">Error Loading Report</h2>
                            <p className="text-gray-600 mb-6">{error || 'Something went wrong. Please try again.'}</p>
                            <button
                                onClick={onBack}
                                className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition"
                            >
                                Go Back
                            </button>
                        </div>
                    </div>
                );
            }

            const agent = data.agent || {};
            const analysis = data.analysis || {};
            const scores = analysis.scores || {};

            return (
                <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
                    <Navbar user={user} onLogin={() => {}} onLogout={onLogout} onAddAgent={onAddAgent} />

                    <div className="max-w-6xl mx-auto px-6 py-8">
                        {/* Back button */}
                        <button
                            onClick={onBack}
                            className="mb-6 text-gray-600 hover:text-gray-900 flex items-center gap-2 transition"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
                            </svg>
                            Back
                        </button>

                        {/* Header */}
                        <div className="bg-gradient-to-br from-blue-600 to-purple-600 rounded-3xl p-8 text-white mb-8 shadow-2xl">
                            <div className="flex flex-col lg:flex-row items-center gap-8">
                                <div className="w-24 h-24 bg-white/20 rounded-2xl flex items-center justify-center text-4xl font-bold">
                                    {(agent.name || 'NA').split(' ').map(n => n[0]).join('')}
                                </div>
                                <div className="flex-1 text-center lg:text-left">
                                    <p className="text-blue-200 text-sm mb-1">Full AI Visibility Report</p>
                                    <h1 className="text-4xl font-extrabold mb-2">{agent.name || 'Unknown Agent'}</h1>
                                    <p className="text-blue-100">{agent.brokerage || 'Unknown'} • {agent.location?.city || 'Unknown'}, {agent.location?.state || ''}</p>
                                </div>
                                <div className="text-center">
                                    <div className="text-6xl font-extrabold mb-1">{scores.overall?.score || 0}</div>
                                    <div className="text-blue-200">Overall Score</div>
                                    <div className="mt-2 px-4 py-1 bg-white/20 rounded-full text-sm font-semibold">
                                        {scores.overall?.tier || 'Unknown'} Tier
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Executive Summary */}
                        <div className="bg-white rounded-3xl p-8 shadow-xl border border-gray-200 mb-8">
                            <h2 className="text-2xl font-bold text-gray-900 mb-4">Executive Summary</h2>
                            <p className="text-gray-700 leading-relaxed text-lg">
                                {analysis.executive_summary || 'No summary available.'}
                            </p>
                        </div>

                        {/* SALT Scores */}
                        <div className="bg-white rounded-3xl p-8 shadow-xl border border-gray-200 mb-8">
                            <h2 className="text-2xl font-bold text-gray-900 mb-6">SALT Score Breakdown</h2>
                            <div className="grid md:grid-cols-2 gap-6">
                                {[
                                    { label: 'Semantic', score: scores.semantic?.score || 0, icon: '🔍', desc: scores.semantic?.grade || 'N/A' },
                                    { label: 'Authority', score: scores.authority?.score || 0, icon: '👑', desc: scores.authority?.grade || 'N/A' },
                                    { label: 'Location', score: scores.location?.score || 0, icon: '📍', desc: scores.location?.grade || 'N/A' },
                                    { label: 'Trust', score: scores.trust?.score || 0, icon: '🛡️', desc: scores.trust?.grade || 'N/A' }
                                ].map((metric, i) => (
                                    <div key={i} className="bg-gradient-to-br from-gray-50 to-gray-100 rounded-2xl p-6 border border-gray-200">
                                        <div className="flex items-center justify-between mb-4">
                                            <div className="flex items-center gap-3">
                                                <span className="text-4xl">{metric.icon}</span>
                                                <div>
                                                    <div className="font-bold text-gray-900">{metric.label}</div>
                                                    <div className="text-sm text-gray-600">Grade: {metric.desc}</div>
                                                </div>
                                            </div>
                                            <span className="text-3xl font-extrabold text-gray-900">{metric.score}</span>
                                        </div>
                                        <div className="h-4 bg-gray-200 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-gradient-to-r from-blue-500 to-purple-600 rounded-full transition-all duration-1000"
                                                style={{width: `${metric.score}%`}}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Recommendations */}
                        {analysis.recommendations && analysis.recommendations.length > 0 && (
                            <div className="bg-gradient-to-br from-emerald-50 to-teal-50 rounded-3xl p-8 border border-emerald-200 shadow-xl">
                                <h2 className="text-2xl font-bold text-gray-900 mb-6">Personalized Action Plan</h2>
                                <div className="space-y-4">
                                    {analysis.recommendations.map((rec, i) => (
                                        <div key={i} className="flex items-start gap-4 bg-white rounded-2xl p-6 shadow-sm">
                                            <span className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-600 text-white rounded-full flex items-center justify-center font-bold">
                                                {i + 1}
                                            </span>
                                            <p className="text-gray-800 leading-relaxed">{rec || ''}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            );
        };

        // ============== MAIN APP ==============
        function App() {
            const [user, setUser] = useState(null);
            const [page, setPage] = useState('search');
            const [agentName, setAgentName] = useState('');
            const [showLoginModal, setShowLoginModal] = useState(false);
            const [showAddAgentModal, setShowAddAgentModal] = useState(false);

            // Check auth on mount
            useEffect(() => {
                fetch('/api/auth/status')
                    .then(r => r.json())
                    .then(d => {
                        if (d.logged_in) {
                            setUser(d);
                        }
                    })
                    .catch(() => {});
            }, []);

            const handleLogin = (userData) => {
                setUser(userData);
                setShowLoginModal(false);
            };

            const handleLogout = async () => {
                await fetch('/api/auth/logout', { method: 'POST' });
                setUser(null);
                setPage('search');
            };

            const handleSearch = (name) => {
                setAgentName(name);
                setPage('snapshot');
            };

            const handleUpgrade = () => {
                if (user?.paid) {
                    setPage('report');
                } else {
                    setPage('paywall');
                }
            };

            const handlePaymentSuccess = (userData) => {
                setUser(userData);
                setPage('report');
            };

            const handleAddAgent = () => {
                setShowAddAgentModal(true);
            };

            const handleAddAgentSuccess = (result) => {
                alert(result.message);
                setShowAddAgentModal(false);
                // Optionally search for the newly added agent
                handleSearch(result.agent_name);
            };

            return (
                <>
                    {page === 'search' && (
                        <SearchPage
                            user={user}
                            onSearch={handleSearch}
                            onLogin={() => setShowLoginModal(true)}
                            onLogout={handleLogout}
                            onAddAgent={handleAddAgent}
                        />
                    )}
                    {page === 'snapshot' && (
                        <SnapshotPage
                            agentName={agentName}
                            user={user}
                            onBack={() => setPage('search')}
                            onUpgrade={handleUpgrade}
                            onLogin={() => setShowLoginModal(true)}
                            onLogout={handleLogout}
                            onAddAgent={handleAddAgent}
                        />
                    )}
                    {page === 'paywall' && (
                        <PaywallPage
                            agentName={agentName}
                            user={user}
                            onBack={() => setPage('snapshot')}
                            onPaymentSuccess={handlePaymentSuccess}
                            onLogout={handleLogout}
                            onAddAgent={handleAddAgent}
                        />
                    )}
                    {page === 'report' && (
                        <FullReportPage
                            agentName={agentName}
                            user={user}
                            onBack={() => setPage('search')}
                            onLogout={handleLogout}
                            onAddAgent={handleAddAgent}
                        />
                    )}

                    <LoginModal
                        show={showLoginModal}
                        onClose={() => setShowLoginModal(false)}
                        onSuccess={handleLogin}
                    />

                    <AddAgentModal
                        show={showAddAgentModal}
                        onClose={() => setShowAddAgentModal(false)}
                        onSuccess={handleAddAgentSuccess}
                    />
                </>
            );
        }

        ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    print(f"Starting Vieweo on http://localhost:{Config.PORT}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
