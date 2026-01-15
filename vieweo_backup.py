"""
Vieweo - AI Visibility Platform for Real Estate Agents
GEO (Generative Engine Optimization) Scoring System
Phase 1: Login → Free Snapshot → Paywall → Full Report
"""

from flask import Flask, jsonify, request, render_template_string, session, Response
from flask_cors import CORS
from dotenv import load_dotenv
import os
import json
import pandas as pd
from datetime import datetime
import secrets

load_dotenv()

from agent_intelligence_v2 import AgentIntelligenceSystem

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
CORS(app)

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

@app.route('/api/auth/upgrade', methods=['POST'])
def upgrade():
    """Simulate payment upgrade"""
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    session['user']['paid'] = True
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

    print(f"Search for '{query}' returned {len(formatted_results)} results:")
    for res in formatted_results[:3]:  # Print first 3
        print(f"  - {res}")

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

    # Check session cache first
    cache_key = f"agent_data_{name.lower()}"
    if cache_key in session:
        print(f"✅ Returning cached data for: {name}")
        cached_data = session[cache_key]
        # Update user status in cached data
        user = session.get('user', {})
        cached_data['user_status'] = {
            'logged_in': bool(user),
            'is_admin': user.get('email') == 'admin@vieweo.com',
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
        return jsonify(result), 404

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
    is_admin = user.get('email') == 'admin@vieweo.com'

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

        'ranking_preview': f"Ranked #{lb.get('state_rank', '?')} of {lb.get('state_total', '?')} in {agent.get('location', {}).get('state', 'Unknown')}" if is_logged_in or is_admin else None,

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

    print(f"✅ Returning data: score={overall_score}, logged_in={is_logged_in}, admin={is_admin}")
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
        print(f"✅ Returning cached full report for: {name}")
        return jsonify(session[cache_key])

    sys = get_system()
    result = sys.analyze_agent(name)

    if 'error' in result:
        return jsonify(result), 404

    # Cache the full report
    session[cache_key] = result
    session.modified = True

    return jsonify(result)

@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    """Leaderboard - requires payment"""
    user = session.get('user', {})
    if not user.get('paid'):
        return jsonify({'error': 'Payment required', 'upgrade_required': True}), 403

    state = request.args.get('state', '')
    city = request.args.get('city', '')
    limit = int(request.args.get('limit', 20))

    sys = get_system()
    df = sys.db.df

    if state:
        df = df[df['State'] == state]
    if city:
        df = df[df['City'] == city]

    top = df.nlargest(limit, 'Credibility_Score')

    return jsonify({
        'count': len(top),
        'agents': [{'rank': i+1, 'name': r['Full_Name'], 'city': r['City'],
                    'state': r['State'], 'score': r['Credibility_Score']}
                   for i, (_, r) in enumerate(top.iterrows())]
    })

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
        from openpyxl import load_workbook

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
            'message': f'Agent {new_agent["Full_Name"]} added successfully'
        })

    except Exception as e:
        print(f"❌ Error adding agent: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to add agent: {str(e)}'}), 500

# ============== FRONTEND ==============

FRONTEND_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vieweo - Be the Agent AI Recommends</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { font-family: 'Inter', -apple-system, sans-serif; }
        .blur-content { filter: blur(8px); pointer-events: none; user-select: none; }
        .gradient-text { background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .animate-in { animation: fadeIn 0.6s ease-out forwards; }
        .score-ring { transition: stroke-dashoffset 1.5s ease-out; }
    </style>
</head>
<body class="bg-gray-50">
    <div id="root"></div>
    <script type="text/babel">
        const { useState, useEffect } = React;
        
        // ============== COMPONENTS ==============
        
        // Lock Icon
        const LockIcon = ({ size = 20 }) => (
            <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0110 0v4"/>
            </svg>
        );
        
        // Score Ring
        const ScoreRing = ({ score, size = 160, label }) => {
            const radius = (size - 16) / 2;
            const circumference = 2 * Math.PI * radius;
            const offset = circumference - (score / 100) * circumference;
            const color = score >= 80 ? '#10b981' : score >= 60 ? '#f59e0b' : '#ef4444';
            
            return (
                <div className="relative" style={{ width: size, height: size }}>
                    <svg width={size} height={size} className="transform -rotate-90">
                        <circle cx={size/2} cy={size/2} r={radius} stroke="#e5e7eb" strokeWidth="12" fill="none"/>
                        <circle cx={size/2} cy={size/2} r={radius} stroke={color} strokeWidth="12" fill="none"
                            strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} className="score-ring"/>
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-4xl font-bold text-gray-900">{score}</span>
                        <span className="text-sm text-gray-500">{label}</span>
                    </div>
                </div>
            );
        };
        
        // Blurred/Locked Section
        const LockedSection = ({ title, children, onUnlock, subtitle = "Unlock with full report", buttonText = "Unlock Now" }) => (
            <div className="relative rounded-2xl border border-gray-200 bg-white p-6 overflow-hidden">
                <div className="blur-content">{children}</div>
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm">
                    <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 mb-3">
                        <LockIcon size={24}/>
                    </div>
                    <h4 className="font-semibold text-gray-900 mb-1">{title}</h4>
                    <p className="text-sm text-gray-500 mb-4">{subtitle}</p>
                    <button onClick={onUnlock} className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition">
                        {buttonText}
                    </button>
                </div>
            </div>
        );
        
        // ============== PAGES ==============
        
        // Login Page
        const LoginPage = ({ onLogin }) => {
            const [name, setName] = useState('');
            const [email, setEmail] = useState('');
            const [loading, setLoading] = useState(false);
            
            const handleSubmit = async (e) => {
                e.preventDefault();
                setLoading(true);
                try {
                    const res = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name, email })
                    });
                    const data = await res.json();
                    if (data.success) onLogin(data.user);
                } catch (err) {
                    alert('Login failed');
                }
                setLoading(false);
            };
            
            return (
                <div className="min-h-screen flex">
                    {/* Left - Form */}
                    <div className="flex-1 flex items-center justify-center p-8">
                        <div className="w-full max-w-md">
                            <div className="mb-8">
                                <h1 className="text-2xl font-bold text-gray-900 mb-2">Welcome to Vieweo</h1>
                                <p className="text-gray-600">Check your AI visibility score and see how often AI platforms recommend you.</p>
                            </div>
                            
                            <form onSubmit={handleSubmit} className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Your Name</label>
                                    <input type="text" value={name} onChange={e => setName(e.target.value)} required
                                        className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                        placeholder="John Smith"/>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                                    <input type="email" value={email} onChange={e => setEmail(e.target.value)} required
                                        className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                        placeholder="john@example.com"/>
                                </div>
                                <button type="submit" disabled={loading}
                                    className="w-full py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition disabled:opacity-50">
                                    {loading ? 'Please wait...' : 'Check My AI Visibility'}
                                </button>
                            </form>
                            
                            <p className="mt-6 text-center text-sm text-gray-500">
                                Used by agents competing for visibility on ChatGPT, Gemini, and Perplexity.
                            </p>
                        </div>
                    </div>
                    
                    {/* Right - Hero */}
                    <div className="hidden lg:flex flex-1 bg-gradient-to-br from-slate-900 to-slate-800 relative overflow-hidden">
                        <img src="https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1200" 
                            className="absolute inset-0 w-full h-full object-cover opacity-40"/>
                        <div className="relative z-10 p-12 flex flex-col justify-center">
                            <h2 className="text-4xl lg:text-5xl font-bold text-white leading-tight mb-6">
                                Be the Agent<br/>AI Recommends.
                            </h2>
                            <p className="text-xl text-gray-300 mb-8">
                                Vieweo measures how often AI platforms recommend you as the best agent in your market.
                            </p>
                            
                            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
                                <h3 className="text-lg font-semibold text-white mb-4">Why GEO Matters for Real Estate</h3>
                                <ul className="space-y-3 text-gray-300 text-sm">
                                    <li className="flex items-start gap-3">
                                        <span className="text-blue-400 mt-1">→</span>
                                        <span>Buyers now ask AI: "Who's the best agent in Rittenhouse?"</span>
                                    </li>
                                    <li className="flex items-start gap-3">
                                        <span className="text-blue-400 mt-1">→</span>
                                        <span>AI platforms answer directly — with only 1 or 2 names</span>
                                    </li>
                                    <li className="flex items-start gap-3">
                                        <span className="text-blue-400 mt-1">→</span>
                                        <span>If AI can't recognize you, it won't recommend you</span>
                                    </li>
                                    <li className="flex items-start gap-3">
                                        <span className="text-blue-400 mt-1">→</span>
                                        <span>GEO = Generative Engine Optimization for AI visibility</span>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            );
        };
        
        // Search Page (after login)
        const SearchPage = ({ user, onSearch, onLogin }) => {
            console.log('SearchPage rendering with user:', user);
            const [query, setQuery] = useState('');
            const [suggestions, setSuggestions] = useState([]);
            const [showLoginModal, setShowLoginModal] = useState(false);
            const [loading, setLoading] = useState(false);

            useEffect(() => {
                console.log('Query changed:', query);
                if (query.length >= 2) {
                    setLoading(true);
                    const timer = setTimeout(() => {
                        console.log('Fetching suggestions for:', query);
                        fetch(`/api/search?q=${encodeURIComponent(query)}`)
                            .then(r => r.json())
                            .then(d => {
                                console.log('Suggestions received:', d);
                                setSuggestions(d.results || []);
                                setLoading(false);
                            })
                            .catch(err => {
                                console.error('Search error:', err);
                                setSuggestions([]);
                                setLoading(false);
                            });
                    }, 150); // 150ms debounce
                    return () => clearTimeout(timer);
                } else {
                    setSuggestions([]);
                    setLoading(false);
                }
            }, [query]);
            
            return (
                <><div className="min-h-screen">
                    {/* Hero Section */}
                    <div className="relative bg-gradient-to-br from-slate-900 to-slate-800 overflow-hidden">
                        <img src="https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1600" 
                            className="absolute inset-0 w-full h-full object-cover opacity-30"/>
                        {/* Login/Signup Button */}
                        <div className="absolute top-4 right-6 z-20">
                            {user ? (
                                <div className="flex items-center gap-3">
                                    <span className="text-white/80 text-sm">Welcome, {user.name || user.first_name}</span>
                                    <button onClick={() => fetch('/api/auth/logout', {method: 'POST'}).then(() => window.location.reload())}
                                        className="px-4 py-2 bg-white/10 backdrop-blur-sm text-white text-sm font-medium rounded-lg hover:bg-white/20 transition border border-white/20">
                                        Logout
                                    </button>
                                </div>
                            ) : (
                                <button onClick={() => setShowLoginModal(true)}
                                    className="px-5 py-2.5 bg-white text-blue-600 text-sm font-semibold rounded-lg hover:bg-blue-50 transition shadow-lg">
                                    Login / Sign Up
                                </button>
                            )}
                        </div>
                        <div className="relative z-10 max-w-6xl mx-auto px-6 py-20">
                            <div className="text-center mb-10">
                                <h1 className="text-4xl lg:text-5xl font-bold text-white mb-4">
                                    Be the Agent AI Recommends.
                                </h1>
                                <p className="text-xl text-gray-300 max-w-2xl mx-auto">
                                    Vieweo measures and improves how often AI platforms recommend you as the best agent in your market.
                                </p>
                            </div>
                            
                            {/* Search Box */}
                            <div className="max-w-2xl mx-auto relative">
                                <div className="flex items-center bg-white rounded-2xl shadow-2xl overflow-hidden">
                                    <div className="pl-6 text-gray-400">
                                        {loading ? (
                                            <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"/>
                                        ) : (
                                            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                                            </svg>
                                        )}
                                    </div>
                                    <input type="text" value={query}
                                        onChange={e => setQuery(e.target.value)}
                                        onKeyDown={e => {
                                            if (e.key === 'Enter') {
                                                e.preventDefault();
                                                if (query) onSearch(query);
                                            }
                                        }}
                                        placeholder="Search by agent name, city, or state..."
                                        className="flex-1 px-4 py-5 text-lg focus:outline-none"/>
                                    <button onClick={() => query && onSearch(query)}
                                        className="m-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition">
                                        Check Visibility
                                    </button>
                                </div>
                                
                                {suggestions.length > 0 && (
                                    <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl shadow-xl border border-gray-100 overflow-hidden z-20 max-h-96 overflow-y-auto">
                                        {suggestions.map(s => (
                                            <button key={s.id} onClick={(e) => { e.preventDefault(); e.stopPropagation(); console.log('Clicked suggestion:', s.name); onSearch(s.name); }}
                                                className="w-full px-6 py-4 text-left hover:bg-gray-50 flex items-center gap-4 border-b border-gray-100 last:border-0">
                                                <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-semibold">
                                                    {s.name ? s.name[0] : '?'}
                                                </div>
                                                <div>
                                                    <div className="font-medium text-gray-900">{s.name}</div>
                                                    <div className="text-sm text-gray-500">{s.city}, {s.state}</div>
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                )}
                                
                                <p className="text-center text-gray-400 text-sm mt-4">
                                    Used by agents competing for visibility on ChatGPT, Gemini, and Perplexity.
                                </p>
                            </div>
                        </div>
                    </div>
                    
                    {/* Why GEO Section */}
                    <div className="max-w-6xl mx-auto px-6 py-16">
                        <h2 className="text-3xl font-bold text-center text-gray-900 mb-4">
                            Why GEO Matters for Real Estate Agents
                        </h2>
                        <p className="text-center text-gray-600 max-w-3xl mx-auto mb-12">
                            Search is changing. Buyers are no longer scrolling through pages of links — they're asking AI who the best agent is in their neighborhood.
                        </p>
                        
                        <div className="grid md:grid-cols-3 gap-8">
                            <div className="bg-white rounded-2xl p-8 border border-gray-200">
                                <div className="w-14 h-14 bg-blue-100 rounded-2xl flex items-center justify-center mb-6">
                                    <svg className="w-7 h-7 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                                    </svg>
                                </div>
                                <h3 className="text-lg font-semibold text-gray-900 mb-2">The Shift</h3>
                                <p className="text-sm font-medium text-gray-700 mb-3">From Search Results → AI Answers</p>
                                <ul className="space-y-2 text-sm text-gray-600">
                                    <li>• Buyers ask: "Who's the best agent in Rittenhouse?"</li>
                                    <li>• AI platforms answer directly — with one or two names</li>
                                </ul>
                            </div>
                            
                            <div className="bg-white rounded-2xl p-8 border border-gray-200">
                                <div className="w-14 h-14 bg-amber-100 rounded-2xl flex items-center justify-center mb-6">
                                    <svg className="w-7 h-7 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                                    </svg>
                                </div>
                                <h3 className="text-lg font-semibold text-gray-900 mb-2">The Problem</h3>
                                <p className="text-sm font-medium text-gray-700 mb-3">Most Agents Are Invisible to AI</p>
                                <ul className="space-y-2 text-sm text-gray-600">
                                    <li>• Have inconsistent online signals</li>
                                    <li>• Strong on Zillow but weak in AI models</li>
                                    <li>• Don't show up across ChatGPT, Gemini, or Perplexity</li>
                                </ul>
                            </div>
                            
                            <div className="bg-white rounded-2xl p-8 border border-gray-200">
                                <div className="w-14 h-14 bg-emerald-100 rounded-2xl flex items-center justify-center mb-6">
                                    <svg className="w-7 h-7 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                    </svg>
                                </div>
                                <h3 className="text-lg font-semibold text-gray-900 mb-2">The Solution</h3>
                                <p className="text-sm font-medium text-gray-700 mb-3">Vieweo = GEO for Real Estate</p>
                                <ul className="space-y-2 text-sm text-gray-600">
                                    <li>• How AI models understand your name & expertise</li>
                                    <li>• How often you're recommended vs. competitors</li>
                                    <li>• What signals are missing or weakening visibility</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                    
                    {/* How It Works */}
                    <div className="bg-slate-900 py-16">
                        <div className="max-w-6xl mx-auto px-6">
                            <h2 className="text-2xl font-bold text-center text-white mb-12">How Vieweo Works</h2>
                            <div className="flex items-center justify-center gap-4 flex-wrap">
                                {[
                                    { icon: '🔍', label: 'Search a location' },
                                    { icon: '📊', label: 'See ranked agents by AI visibility' },
                                    { icon: '📈', label: 'View your VEO Score' },
                                    { icon: '✅', label: 'Get clear actions to improve' }
                                ].map((step, i) => (
                                    <React.Fragment key={i}>
                                        <div className="flex flex-col items-center gap-2">
                                            <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center text-2xl">
                                                {step.icon}
                                            </div>
                                            <span className="text-sm text-gray-400 text-center">{step.label}</span>
                                        </div>
                                        {i < 3 && <span className="text-gray-600 text-2xl">→</span>}
                                    </React.Fragment>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
                <LoginModal show={showLoginModal} onClose={() => setShowLoginModal(false)} onSuccess={onLogin}/>
                </>
            );
        };
        
        // Free Snapshot Page (blurred sections)
        // Opus-style Loading Component
        const OpusLoader = ({ title = "Analyzing", subtitle = "AI processing in progress" }) => {
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
                }, 2000);

                return () => {
                    clearInterval(dotsTimer);
                    clearInterval(stepTimer);
                };
            }, []);

            return (
                <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950 flex items-center justify-center p-6 relative overflow-hidden">
                    {/* Animated background gradient orbs */}
                    <div className="absolute inset-0 overflow-hidden">
                        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" style={{animationDuration: '4s'}}/>
                        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse" style={{animationDuration: '6s', animationDelay: '1s'}}/>
                    </div>

                    <div className="relative z-10 text-center max-w-2xl w-full">
                        {/* Main spinner */}
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

                        {/* Title */}
                        <h2 className="text-3xl font-bold text-white mb-3">
                            {title}{dots}
                        </h2>

                        {/* Subtitle */}
                        <p className="text-blue-200/60 text-lg mb-8">{subtitle}</p>

                        {/* Animated thinking steps */}
                        <div className="bg-slate-900/40 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-6 shadow-2xl">
                            <div className="space-y-3">
                                {steps.map((step, idx) => {
                                    const isPast = idx < stepIndex;
                                    const isCurrent = idx === stepIndex;
                                    const isFuture = idx > stepIndex;

                                    return (
                                        <div key={idx} className="flex items-center gap-3 transition-all duration-500">
                                            {/* Status icon */}
                                            <div className={`w-6 h-6 rounded-full flex items-center justify-center transition-all duration-500 ${
                                                isPast ? 'bg-green-500/20 border-2 border-green-500' :
                                                isCurrent ? 'bg-blue-500/20 border-2 border-blue-500 animate-pulse' :
                                                'bg-slate-700/20 border-2 border-slate-600'
                                            }`}>
                                                {isPast && <svg className="w-3 h-3 text-green-400" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/></svg>}
                                                {isCurrent && <div className="w-2 h-2 bg-blue-400 rounded-full animate-ping"/>}
                                            </div>

                                            {/* Step text */}
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

                        {/* Bottom hint */}
                        <p className="text-slate-500 text-xs mt-6 animate-pulse">
                            Powered by Gemini AI
                        </p>
                    </div>
                </div>
            );
        };

        // Login Modal Component (reusable)
        const LoginModal = ({ show, onClose, onSuccess }) => {
            if (!show) return null;
            return (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
                    <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-8 relative animate-in">
                        <button onClick={onClose} className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100">
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/></svg>
                        </button>
                        <div className="text-center mb-6">
                            <div className="w-14 h-14 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                                <svg className="w-7 h-7 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
                            </div>
                            <h3 className="text-xl font-bold text-gray-900">Login to Vieweo</h3>
                            <p className="text-sm text-gray-500 mt-1">Access SALT scores and detailed insights</p>
                        </div>
                        <form onSubmit={async (e) => { e.preventDefault(); const fd = new FormData(e.target); try { const r = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: fd.get('first_name') + ' ' + fd.get('last_name'), email: fd.get('email') }) }); const d = await r.json(); if (d.success) { onClose(); if (onSuccess) onSuccess(d.user); else window.location.reload(); } } catch { alert('Login failed'); } }} className="space-y-4">
                            <div className="grid grid-cols-2 gap-3">
                                <div><label className="block text-xs font-medium text-gray-700 mb-1">First Name</label><input name="first_name" type="text" required className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm" placeholder="John"/></div>
                                <div><label className="block text-xs font-medium text-gray-700 mb-1">Last Name</label><input name="last_name" type="text" required className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm" placeholder="Smith"/></div>
                            </div>
                            <div><label className="block text-xs font-medium text-gray-700 mb-1">Email</label><input name="email" type="email" required className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm" placeholder="john@example.com"/></div>
                            <button type="submit" className="w-full py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700">Sign In</button>
                        </form>
                    </div>
                </div>
            );
        };
        
        const SnapshotPage = ({ agentName, user, onUpgrade, onBack }) => {
            const [data, setData] = useState(null);
            const [loading, setLoading] = useState(true);
            const [showLoginModal, setShowLoginModal] = useState(false);

            useEffect(() => {
                console.log('SnapshotPage: Fetching data for:', agentName);
                setLoading(true);
                fetch(`/api/visibility/free?name=${encodeURIComponent(agentName)}`)
                    .then(r => {
                        console.log('Response status:', r.status);
                        return r.json();
                    })
                    .then(d => {
                        console.log('Snapshot data received:', d);
                        setData(d);
                        setLoading(false);
                    })
                    .catch(err => {
                        console.error('Error fetching snapshot:', err);
                        setData({error: 'Failed to load data'});
                        setLoading(false);
                    });
            }, [agentName]);
            
            if (loading) return <OpusLoader title="Analyzing Visibility" subtitle="Computing AI discoverability metrics"/>;
            
            if (!data || data.error) return (
                <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-6">
                    <div className="max-w-md w-full bg-white rounded-3xl shadow-xl border border-gray-100 p-8 text-center">
                        {/* Icon */}
                        <div className="w-20 h-20 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-6">
                            <svg className="w-10 h-10 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01"/>
                            </svg>
                        </div>
                        
                        {/* Title */}
                        <h2 className="text-2xl font-bold text-gray-900 mb-2">Agent Not Found</h2>
                        <p className="text-gray-500 mb-6">
                            We couldn't find <span className="font-semibold text-gray-700">"{agentName}"</span> in our database.
                        </p>
                        
                        {/* Suggestions */}
                        <div className="bg-gray-50 rounded-2xl p-5 mb-6 text-left">
                            <p className="text-sm font-medium text-gray-700 mb-3">Try the following:</p>
                            <ul className="space-y-2 text-sm text-gray-600">
                                <li className="flex items-start gap-2">
                                    <span className="text-blue-500 mt-0.5">•</span>
                                    <span>Check the spelling of the agent's name</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-blue-500 mt-0.5">•</span>
                                    <span>Search by first name only (e.g., "Ben")</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <span className="text-blue-500 mt-0.5">•</span>
                                    <span>Try searching by city or state name</span>
                                </li>
                            </ul>
                        </div>
                        
                        {/* Action Buttons */}
                        <div className="flex flex-col sm:flex-row gap-3">
                            <button onClick={onBack} className="flex-1 px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition flex items-center justify-center gap-2">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                                </svg>
                                Search Again
                            </button>
                        </div>
                        
                        {/* Help text */}
                        <p className="text-xs text-gray-400 mt-6">
                            Our database includes real estate agents from major US markets.
                        </p>
                    </div>
                </div>
            );
            
            const isLoggedIn = data.user_status?.logged_in;
            const isAdmin = data.user_status?.is_admin;

            return (
                <div className="min-h-screen bg-gray-50">
                    {/* Header */}
                    <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
                        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
                            <button onClick={onBack} className="text-gray-600 hover:text-gray-900 flex items-center gap-2">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
                                </svg>
                                Back
                            </button>
                            <div className="flex items-center gap-3">
                                {isLoggedIn ? (
                                    <>
                                        {isAdmin && <span className="px-3 py-1 bg-purple-100 text-purple-700 text-xs font-semibold rounded-full">ADMIN</span>}
                                        <span className="text-sm text-gray-500">Logged in as</span>
                                        <span className="font-medium text-gray-900">{user?.name || 'User'}</span>
                                    </>
                                ) : (
                                    <button onClick={() => setShowLoginModal(true)} className="px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700">
                                        Login to See SALT Scores
                                    </button>
                                )}
                            </div>
                        </div>
                    </header>
                    
                    <main className="max-w-6xl mx-auto px-6 py-8">
                        {/* Agent Header */}
                        <div className="bg-white rounded-2xl p-8 border border-gray-200 mb-8 animate-in">
                            <div className="flex flex-col lg:flex-row items-center gap-8">
                                <div className="w-24 h-24 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center text-white text-3xl font-bold shadow-lg">
                                    {data.agent.name.split(' ').map(n => n[0]).join('')}
                                </div>
                                <div className="flex-1 text-center lg:text-left">
                                    <h1 className="text-2xl font-bold text-gray-900 mb-1">{data.agent.name}</h1>
                                    <p className="text-gray-600">{data.agent.brokerage}</p>
                                    <p className="text-gray-500 text-sm">{data.agent.city}, {data.agent.state}</p>
                                </div>
                                <ScoreRing score={data.visibility_score} label="AI Visibility"/>
                            </div>
                        </div>
                        
                        {/* Free Metrics */}
                        <div className="grid md:grid-cols-3 gap-6 mb-8">
                            <div className="bg-white rounded-2xl p-6 border border-gray-200 animate-in" style={{animationDelay: '0.1s'}}>
                                <h3 className="text-sm font-medium text-gray-500 mb-2">Visibility Tier</h3>
                                <p className="text-2xl font-bold text-gray-900">{data.visibility_tier}</p>
                                <p className="text-sm text-gray-500 mt-1">Grade: {data.visibility_grade}</p>
                            </div>
                            <div className="bg-white rounded-2xl p-6 border border-gray-200 animate-in" style={{animationDelay: '0.2s'}}>
                                <h3 className="text-sm font-medium text-gray-500 mb-2">Market Presence</h3>
                                <p className="text-2xl font-bold text-gray-900">{data.market_presence}</p>
                                <p className="text-sm text-gray-500 mt-1">In your local market</p>
                            </div>
                            <div className="bg-white rounded-2xl p-6 border border-gray-200 animate-in" style={{animationDelay: '0.3s'}}>
                                <h3 className="text-sm font-medium text-gray-500 mb-2">AI Discoverability</h3>
                                <p className="text-2xl font-bold text-gray-900">{data.ai_discoverability}</p>
                                <p className="text-sm text-gray-500 mt-1">Across AI platforms</p>
                            </div>
                        </div>
                        
                        {/* Teaser Ranking */}
                        <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-2xl p-6 mb-8 text-white animate-in" style={{animationDelay: '0.4s'}}>
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-blue-200 text-sm mb-1">Your Ranking Preview</p>
                                    <p className="text-2xl font-bold">{data.ranking_teaser}</p>
                                </div>
                                <button onClick={onUpgrade} className="px-6 py-3 bg-white text-blue-600 font-semibold rounded-xl hover:bg-blue-50 transition">
                                    See Full Leaderboard
                                </button>
                            </div>
                        </div>
                        
                        {/* Locked Sections */}
                        <div className="grid md:grid-cols-2 gap-6 mb-8">
                            <LockedSection title="Competitor Analysis" onUnlock={onUpgrade}>
                                <div className="space-y-4">
                                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                                        <div className="w-10 h-10 bg-gray-200 rounded-full"/>
                                        <div className="flex-1"><div className="h-4 bg-gray-200 rounded w-3/4"/></div>
                                        <div className="h-6 w-16 bg-gray-200 rounded"/>
                                    </div>
                                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                                        <div className="w-10 h-10 bg-gray-200 rounded-full"/>
                                        <div className="flex-1"><div className="h-4 bg-gray-200 rounded w-2/3"/></div>
                                        <div className="h-6 w-16 bg-gray-200 rounded"/>
                                    </div>
                                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                                        <div className="w-10 h-10 bg-gray-200 rounded-full"/>
                                        <div className="flex-1"><div className="h-4 bg-gray-200 rounded w-4/5"/></div>
                                        <div className="h-6 w-16 bg-gray-200 rounded"/>
                                    </div>
                                </div>
                            </LockedSection>
                            
                            {user && data.executive_summary?.salt_scores ? (
                                <div className="bg-white rounded-2xl border border-gray-200 p-6">
                                    <h3 className="font-semibold text-gray-900 mb-4">SALT Score Breakdown</h3>
                                    <div className="space-y-4">
                                        <div><div className="flex justify-between mb-1"><span>Semantic</span><span>{data.executive_summary.salt_scores.semantic}</span></div><div className="h-2 bg-gray-200 rounded-full"><div className="h-full bg-blue-600 rounded-full" style={{width: `${data.executive_summary.salt_scores.semantic}%`}}/></div></div>
                                        <div><div className="flex justify-between mb-1"><span>Authority</span><span>{data.executive_summary.salt_scores.authority}</span></div><div className="h-2 bg-gray-200 rounded-full"><div className="h-full bg-blue-600 rounded-full" style={{width: `${data.executive_summary.salt_scores.authority}%`}}/></div></div>
                                        <div><div className="flex justify-between mb-1"><span>Location</span><span>{data.executive_summary.salt_scores.location}</span></div><div className="h-2 bg-gray-200 rounded-full"><div className="h-full bg-blue-600 rounded-full" style={{width: `${data.executive_summary.salt_scores.location}%`}}/></div></div>
                                        <div><div className="flex justify-between mb-1"><span>Trust</span><span>{data.executive_summary.salt_scores.trust}</span></div><div className="h-2 bg-gray-200 rounded-full"><div className="h-full bg-blue-600 rounded-full" style={{width: `${data.executive_summary.salt_scores.trust}%`}}/></div></div>
                                    </div>
                                </div>
                            ) : (
                                <LockedSection title="SALT Score Breakdown" onUnlock={() => setShowLoginModal(true)} subtitle="Login to view scores" buttonText="Login to Unlock">
                                    <div className="space-y-4">
                                        <div><div className="flex justify-between mb-1"><span>Semantic</span><span>--</span></div><div className="h-2 bg-gray-200 rounded-full"/></div>
                                        <div><div className="flex justify-between mb-1"><span>Authority</span><span>--</span></div><div className="h-2 bg-gray-200 rounded-full"/></div>
                                        <div><div className="flex justify-between mb-1"><span>Location</span><span>--</span></div><div className="h-2 bg-gray-200 rounded-full"/></div>
                                        <div><div className="flex justify-between mb-1"><span>Trust</span><span>--</span></div><div className="h-2 bg-gray-200 rounded-full"/></div>
                                    </div>
                                </LockedSection>
                            )}
                        </div>
                        
                        {/* CTA */}
                        <div className="mt-16 text-center animate-in" style={{animationDelay: '0.5s'}}>
                            <h3 className="text-xl font-bold text-gray-900 mb-2">Unlock Your Full AI Visibility Report</h3>
                            <p className="text-gray-600 mb-6">Get detailed SALT scores, competitor analysis, and actionable GEO improvements.</p>
                            <button onClick={onUpgrade} className="px-8 py-4 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition text-lg shadow-lg shadow-blue-600/25">
                                Unlock Full Report — $49
                            </button>
                            <p className="text-sm text-gray-500 mt-3">One-time payment. 3-page detailed report.</p>
                        </div>
                    </main>
                </div>
            );
        };

        // Paywall Page
        const PaywallPage = ({ agentName, user, onPaymentSuccess, onBack }) => {
            const [processing, setProcessing] = useState(false);
            
            const handlePayment = async () => {
                setProcessing(true);
                // Simulate payment
                await new Promise(r => setTimeout(r, 1500));
                try {
                    const res = await fetch('/api/auth/upgrade', { method: 'POST' });
                    const data = await res.json();
                    if (data.success) onPaymentSuccess(data.user);
                } catch (err) {
                    alert('Payment failed');
                }
                setProcessing(false);
            };
            
            return (
                <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
                    <div className="max-w-lg w-full">
                        <button onClick={onBack} className="text-gray-600 hover:text-gray-900 mb-8 flex items-center gap-2">
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
                            </svg>
                            Back
                        </button>
                        
                        <div className="bg-white rounded-3xl p-8 shadow-xl border border-gray-100">
                            <div className="text-center mb-8">
                                <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                                    <svg className="w-8 h-8 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                                    </svg>
                                </div>
                                <h2 className="text-2xl font-bold text-gray-900 mb-2">Unlock Full GEO Report</h2>
                                <p className="text-gray-600">One-time AI Visibility Report (3 Pages)</p>
                            </div>
                            
                            <div className="bg-gray-50 rounded-2xl p-6 mb-6">
                                <div className="flex items-baseline justify-center gap-1 mb-4">
                                    <span className="text-4xl font-bold text-gray-900">$49</span>
                                    <span className="text-gray-500">one-time</span>
                                </div>
                                
                                <ul className="space-y-3">
                                    {[
                                        'Page 1: Visibility Snapshot (Overall Score & Benchmarks)',
                                        'Page 2: SALT Deep Dive (Gaps & Risks)',
                                        'Page 3: Actionable Intelligence (5 Quick Wins)'
                                    ].map((item, i) => (
                                        <li key={i} className="flex items-start gap-3 text-sm">
                                            <svg className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                                            </svg>
                                            <span className="text-gray-700">{item}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            
                            <div className="space-y-3 mb-6 text-sm text-gray-600">
                                <div className="flex items-center gap-2">
                                    <svg className="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                                    </svg>
                                    Full leaderboard access
                                </div>
                                <div className="flex items-center gap-2">
                                    <svg className="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                                    </svg>
                                    Competitor comparison
                                </div>
                                <div className="flex items-center gap-2">
                                    <svg className="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                                    </svg>
                                    Detailed GEO signals
                                </div>
                            </div>
                            
                            <button onClick={handlePayment} disabled={processing}
                                className="w-full py-4 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition disabled:opacity-50">
                                {processing ? 'Processing...' : 'Complete Purchase'}
                            </button>
                            
                            <p className="text-center text-xs text-gray-500 mt-4">
                                Secure payment. Instant access to your report.
                            </p>
                        </div>
                    </div>
                </div>
            );
        };
        
        // Full Report Page (after payment)
        const FullReportPage = ({ agentName, user, onBack }) => {
            const [data, setData] = useState(null);
            const [loading, setLoading] = useState(true);
            const [error, setError] = useState(null);
            const [showLoginModal, setShowLoginModal] = useState(false);
            
            useEffect(() => {
                console.log('FullReportPage: Fetching data for:', agentName);
                setLoading(true);
                setError(null);
                fetch(`/api/visibility/full?name=${encodeURIComponent(agentName)}`)
                    .then(r => {
                        console.log('Full report response status:', r.status);
                        if (!r.ok) {
                            throw new Error(`HTTP ${r.status}: ${r.statusText}`);
                        }
                        return r.json();
                    })
                    .then(d => {
                        console.log('Full report data received:', d);
                        if (d.error) {
                            console.error('API returned error:', d.error);
                            setError(d.error);
                            setData(null);
                        } else {
                            console.log('Setting data - has agent:', !!d.agent, 'has analysis:', !!d.analysis);
                            setData(d);
                        }
                        setLoading(false);
                    })
                    .catch(e => {
                        console.error('Error fetching report:', e);
                        setError(e.message);
                        setData(null);
                        setLoading(false);
                    });
            }, [agentName]);
            
            if (loading) return <OpusLoader title="Generating Full Report" subtitle="Comprehensive AI visibility analysis"/>;
            
            if (error || !data || data.error) return (
                <div className="min-h-screen flex items-center justify-center">
                    <div className="text-center">
                        <p className="text-red-600 mb-4">{data?.error || error || 'Error loading report'}</p>
                        <button onClick={onBack} className="px-4 py-2 bg-blue-600 text-white rounded-lg">Go Back</button>
                    </div>
                </div>
            );
            
            const agent = data.agent || {};
            const analysis = data.analysis || {};
            const scores = analysis.scores || {};
            
            return (
                <div className="min-h-screen bg-gray-50">
                    <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
                        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
                            <button onClick={onBack} className="text-gray-600 hover:text-gray-900 flex items-center gap-2">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
                                </svg>
                                Back
                            </button>
                            <span className="px-3 py-1 bg-emerald-100 text-emerald-700 text-sm font-medium rounded-full">
                                ✓ Full Report Unlocked
                            </span>
                        </div>
                    </header>
                    
                    <main className="max-w-6xl mx-auto px-6 py-8">
                        {/* Report Header */}
                        <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-3xl p-8 text-white mb-8">
                            <div className="flex flex-col lg:flex-row items-center gap-8">
                                <div className="w-24 h-24 bg-white/20 rounded-2xl flex items-center justify-center text-3xl font-bold">
                                    {(agent.name || 'NA').split(' ').map(n => n[0]).join('')}
                                </div>
                                <div className="flex-1 text-center lg:text-left">
                                    <p className="text-blue-200 text-sm mb-1">AI Visibility Report</p>
                                    <h1 className="text-3xl font-bold mb-2">{agent.name || 'Unknown Agent'}</h1>
                                    <p className="text-blue-100">{agent.brokerage || 'Unknown Brokerage'} • {agent.location?.city || 'Unknown'}, {agent.location?.state || ''}</p>
                                </div>
                                <div className="text-center">
                                    <div className="text-5xl font-bold mb-1">{scores.overall?.score || 0}</div>
                                    <div className="text-blue-200">Overall Score</div>
                                    <div className="mt-2 px-4 py-1 bg-white/20 rounded-full text-sm">
                                        {scores.overall?.tier || 'Unknown'} Tier
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        {/* Page 1: Visibility Snapshot */}
                        <div className="bg-white rounded-2xl p-8 border border-gray-200 mb-8">
                            <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                                <span className="w-8 h-8 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center text-sm font-bold">1</span>
                                Visibility Snapshot
                            </h2>
                            
                            <div className="grid md:grid-cols-4 gap-4 mb-8">
                                {[
                                    { label: 'Authority', score: scores.authority?.score, grade: scores.authority?.grade },
                                    { label: 'Sentiment', score: scores.sentiment?.score, grade: scores.sentiment?.grade },
                                    { label: 'Trust', score: scores.trustworthiness?.score, grade: scores.trustworthiness?.grade },
                                    { label: 'Location', score: scores.location_visibility?.score, grade: scores.location_visibility?.grade }
                                ].map((item, i) => (
                                    <div key={i} className="bg-gray-50 rounded-xl p-4 text-center">
                                        <div className="text-3xl font-bold text-gray-900 mb-1">{item.score || 0}</div>
                                        <div className="text-sm text-gray-500 mb-2">{item.label}</div>
                                        <span className={`px-2 py-1 text-xs font-semibold rounded ${
                                            item.grade?.startsWith('A') ? 'bg-emerald-100 text-emerald-700' :
                                            item.grade?.startsWith('B') ? 'bg-blue-100 text-blue-700' :
                                            'bg-amber-100 text-amber-700'
                                        }`}>{item.grade}</span>
                                    </div>
                                ))}
                            </div>
                            
                            {/* Leaderboard Position */}
                            {data.leaderboard_context && (
                                <div className="bg-blue-50 rounded-xl p-6">
                                    <h3 className="font-semibold text-gray-900 mb-4">Your Leaderboard Position</h3>
                                    <div className="grid md:grid-cols-3 gap-4">
                                        <div className="text-center">
                                            <div className="text-2xl font-bold text-blue-600">#{data.leaderboard_context.state_rank}</div>
                                            <div className="text-sm text-gray-600">in {agent.location?.state} ({data.leaderboard_context.state_total} agents)</div>
                                        </div>
                                        <div className="text-center">
                                            <div className="text-2xl font-bold text-blue-600">#{data.leaderboard_context.city_rank}</div>
                                            <div className="text-sm text-gray-600">in {agent.location?.city} ({data.leaderboard_context.city_total} agents)</div>
                                        </div>
                                        <div className="text-center">
                                            <div className="text-2xl font-bold text-blue-600">Top {data.leaderboard_context.percentile}%</div>
                                            <div className="text-sm text-gray-600">Nationally</div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                        
                        {/* Page 2: Deep Dive */}
                        <div className="bg-white rounded-2xl p-8 border border-gray-200 mb-8">
                            <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                                <span className="w-8 h-8 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center text-sm font-bold">2</span>
                                SALT Deep Dive (Gaps & Risks)
                            </h2>
                            
                            <div className="grid md:grid-cols-2 gap-6">
                                {['authority', 'sentiment', 'trustworthiness', 'location_visibility'].map(key => {
                                    const score = scores[key];
                                    if (!score) return null;
                                    return (
                                        <div key={key} className="border border-gray-200 rounded-xl p-6">
                                            <div className="flex items-center justify-between mb-4">
                                                <h3 className="font-semibold text-gray-900 capitalize">{key.replace('_', ' ')}</h3>
                                                <span className={`px-3 py-1 text-sm font-semibold rounded-full ${
                                                    score.grade?.startsWith('A') ? 'bg-emerald-100 text-emerald-700' :
                                                    score.grade?.startsWith('B') ? 'bg-blue-100 text-blue-700' :
                                                    'bg-amber-100 text-amber-700'
                                                }`}>{score.score} / {score.grade}</span>
                                            </div>
                                            <div className="h-2 bg-gray-100 rounded-full mb-4 overflow-hidden">
                                                <div className="h-full bg-blue-600 rounded-full" style={{width: `${score.score}%`}}/>
                                            </div>
                                            <ul className="space-y-2">
                                                {score.factors?.slice(0, 4).map((f, i) => (
                                                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                                                        <svg className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                                                        </svg>
                                                        {f}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                        
                        {/* Critical Issues & Red Flags */}
                        {analysis.actionable_insights?.geo_weaknesses && analysis.actionable_insights.geo_weaknesses.length > 0 && (
                            <div className="bg-red-50 border-2 border-red-200 rounded-2xl p-6 mb-8">
                                <h2 className="text-xl font-bold text-red-900 mb-4 flex items-center gap-2">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4v2m0 4v2m-6-4a2 2 0 11-4 0 2 2 0 014 0zM7 20a7 7 0 1114 0M12 13a3 3 0 11-6 0 3 3 0 016 0z"/>
                                    </svg>
                                    Critical GEO Visibility Issues
                                </h2>
                                <p className="text-sm text-red-800 mb-4">These gaps are preventing AI discovery and should be addressed immediately:</p>
                                <ul className="space-y-3">
                                    {analysis.actionable_insights.geo_weaknesses.map((w, i) => (
                                        <li key={i} className="flex items-start gap-3 text-sm text-red-900">
                                            <span className="inline-block w-5 h-5 bg-red-600 text-white rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold">{i+1}</span>
                                            <span>{w}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        
                        {/* Page 3: Detailed GEO Improvement Roadmap */}
                        <div className="bg-white rounded-2xl p-8 border border-gray-200 mb-8">
                            <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                                <span className="w-8 h-8 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center text-sm font-bold">3</span>
                                GEO Improvement Roadmap
                            </h2>
                            
                            {/* Critical Issues */}
                            {analysis.geo_improvement_roadmap?.critical_issues && analysis.geo_improvement_roadmap.critical_issues.length > 0 && (
                                <div className="mb-8">
                                    <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                                        <span className="px-3 py-1 bg-red-100 text-red-700 rounded-full text-xs font-bold">CRITICAL</span>
                                        Address Immediately
                                    </h3>
                                    <ul className="space-y-2 border-l-4 border-red-500 pl-4">
                                        {analysis.geo_improvement_roadmap.critical_issues.map((item, i) => {
                                            const parts = (item || '').split(':');
                                            return (
                                                <li key={i} className="text-sm text-gray-700">
                                                    {parts.length > 1 ? (
                                                        <><span className="font-semibold text-red-600">{parts[0]}:</span> {parts.slice(1).join(':')}</>
                                                    ) : item}
                                                </li>
                                            );
                                        })}
                                    </ul>
                                </div>
                            )}
                            
                            {/* High Priority */}
                            {analysis.geo_improvement_roadmap?.high_priority && analysis.geo_improvement_roadmap.high_priority.length > 0 && (
                                <div className="mb-8">
                                    <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                                        <span className="px-3 py-1 bg-amber-100 text-amber-700 rounded-full text-xs font-bold">HIGH PRIORITY</span>
                                        3-6 Month Plan
                                    </h3>
                                    <div className="grid md:grid-cols-2 gap-4">
                                        {analysis.geo_improvement_roadmap.high_priority.map((item, i) => {
                                            const parts = (item || '').split(':');
                                            return (
                                                <div key={i} className="bg-amber-50 rounded-lg p-4 border border-amber-200">
                                                    <h4 className="font-semibold text-amber-900 text-sm mb-2">{parts[0]}</h4>
                                                    <p className="text-sm text-amber-800">{parts.length > 1 ? parts.slice(1).join(':') : ''}</p>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}
                            
                            {/* Quick Wins */}
                            {analysis.geo_improvement_roadmap?.quick_wins && analysis.geo_improvement_roadmap.quick_wins.length > 0 && (
                                <div className="mb-8">
                                    <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                                        <span className="px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-xs font-bold">QUICK WINS</span>
                                        Easy & High Impact
                                    </h3>
                                    <div className="grid md:grid-cols-2 gap-3">
                                        {analysis.geo_improvement_roadmap.quick_wins.map((item, i) => (
                                            <div key={i} className="flex items-start gap-3 bg-emerald-50 rounded-lg p-4 border border-emerald-200">
                                                <svg className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                                                </svg>
                                                <div className="text-sm text-emerald-900">{item || ''}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            {/* Estimated Impact */}
                            {analysis.geo_improvement_roadmap?.estimated_impact && (
                                <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                                    <p className="text-sm text-blue-900">
                                        <span className="font-semibold">📈 Potential Impact:</span> {analysis.geo_improvement_roadmap.estimated_impact}
                                    </p>
                                </div>
                            )}
                        </div>
                        
                        {/* Page 4: Action Plan */}
                        <div className="bg-white rounded-2xl p-8 border border-gray-200 mb-8">
                            <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                                <span className="w-8 h-8 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center text-sm font-bold">4</span>
                                Actionable Intelligence (Strengths & Improvement Areas)
                            </h2>
                            
                            <div className="grid md:grid-cols-2 gap-6 mb-8">
                                <div>
                                    <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                        <span className="text-emerald-500">✓</span> Strengths
                                    </h3>
                                    <ul className="space-y-2">
                                        {(analysis.profile_analysis?.strengths || []).map((s, i) => (
                                            <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                                                <span className="text-emerald-500">•</span> {s || ''}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                                <div>
                                    <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                        <span className="text-red-500">⚠</span> Critical Gaps
                                    </h3>
                                    <ul className="space-y-2">
                                        {(analysis.profile_analysis?.areas_for_improvement || []).map((a, i) => (
                                            <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                                                <span className="text-red-500">•</span> {a || ''}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                            
                            {/* Detailed GEO Recommendations */}
                            <div className="space-y-4">
                                <h3 className="font-semibold text-gray-900 mb-4">Detailed GEO Improvement Strategy</h3>
                                {(analysis.recommendations?.for_agent || []).map((rec, i) => (
                                    <div key={i} className="bg-gradient-to-r from-blue-50 to-blue-100 rounded-lg p-5 border border-blue-200">
                                        <div className="flex items-start gap-3">
                                            <span className="inline-block w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold">
                                                {i + 1}
                                            </span>
                                            <p className="text-sm text-gray-800 leading-relaxed">{rec || ''}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                        
                        {/* Executive Summary */}
                        <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-8 text-white">
                            <h2 className="text-xl font-bold mb-4">Executive Summary</h2>
                            <p className="text-gray-300 leading-relaxed">{analysis.executive_summary || 'No summary available.'}</p>
                        </div>
                    </main>
                </div>
            );
        };

        // ============== MAIN APP ==============
        
        function App() {
            const [user, setUser] = useState(null);
            const [page, setPage] = useState('search'); // login (commented out), search, snapshot, paywall, report
            const [agentName, setAgentName] = useState('');

            // Check auth on mount
            useEffect(() => {
                console.log('App mounted, checking auth...');
                fetch('/api/auth/status')
                    .then(r => r.json())
                    .then(d => {
                        console.log('Auth response:', d);
                        if (d.logged_in) {
                            setUser(d);
                            setPage('search');
                        }
                    })
                    .catch(err => console.error('Auth check failed:', err));
            }, []);
            
            const handleLogin = (userData) => {
                setUser(userData);
                setPage('search');
            };
            
            const handleSearch = (name) => {
                console.log('handleSearch called with name:', name);
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
            
            // Render pages
            console.log('Rendering page:', page, 'User:', user);

            // Commented out login page - dashboard is now the landing page
            // if (page === 'login') return <LoginPage onLogin={handleLogin}/>;
            if (page === 'search') return <SearchPage user={user} onSearch={handleSearch} onLogin={handleLogin}/>;
            if (page === 'snapshot') return <SnapshotPage agentName={agentName} user={user} onUpgrade={handleUpgrade} onBack={() => setPage('search')}/>;
            if (page === 'paywall') return <PaywallPage agentName={agentName} user={user} onPaymentSuccess={handlePaymentSuccess} onBack={() => setPage('snapshot')}/>;
            if (page === 'report') return <FullReportPage agentName={agentName} user={user} onBack={() => setPage('search')}/>;

            return <div className="min-h-screen flex items-center justify-center"><div className="text-gray-500">Loading...</div></div>;
        }
        
        ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return Response(FRONTEND_HTML, mimetype='text/html')

# ============== MAIN ==============

def run_server():
    print(f"""
============================================================
       VIEWEO - AI Visibility Platform
       GEO for Real Estate Agents
============================================================
Server: http://localhost:{Config.PORT}
Gemini: {'Enabled' if Config.GEMINI_API_KEY else 'Disabled'}
============================================================
    """)
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)

if __name__ == '__main__':
    run_server()