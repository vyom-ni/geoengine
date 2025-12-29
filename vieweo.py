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

def get_system():
    global system
    if system is None:
        excel_path = Config.EXCEL_PATH
        for path in [Config.EXCEL_PATH, 'US_Real_Estate_Agents_Database.xlsx', 
                     'US_Real_Estate_Agents_Database__2_.xlsx', 
                     '/mnt/user-data/uploads/US_Real_Estate_Agents_Database__2_.xlsx',
                     'data/US_Real_Estate_Agents_Database.xlsx']:
            if os.path.exists(path):
                excel_path = path
                break
        system = AgentIntelligenceSystem(excel_path, Config.GEMINI_API_KEY)
    return system

# ============== API ROUTES ==============

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Simple login - store name/email in session"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    
    if not name or not email:
        return jsonify({'error': 'Name and email are required'}), 400
    
    # Check for admin credentials
    is_admin = email.lower() == 'admin@gmail.com' and name.lower() == 'admin'
    
    session['user'] = {
        'name': name, 
        'email': email, 
        'logged_in': True, 
        'paid': is_admin,  # Admin gets free access
        'is_admin': is_admin
    }
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
    
    return jsonify({
        'count': len(results),
        'results': [{'id': r.get('Agent_ID'), 'name': r.get('Full_Name'), 
                     'city': r.get('City'), 'state': r.get('State')} for r in results]
    })

@app.route('/api/visibility/free', methods=['GET'])
def free_visibility():
    """Free visibility snapshot - limited data"""
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Agent name required'}), 400
    
    try:
        sys = get_system()
        result = sys.analyze_agent(name)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    if 'error' in result:
        return jsonify(result), 404
    
    # Return LIMITED free data
    agent = result['agent']
    analysis = result['analysis']
    lb = result.get('leaderboard_context', {})
    
    return jsonify({
        'agent': {
            'name': agent['name'],
            'city': agent['location']['city'],
            'state': agent['location']['state'],
            'brokerage': agent['brokerage']
        },
        'visibility_score': analysis['scores']['overall']['score'],
        'visibility_grade': analysis['scores']['overall']['grade'],
        'visibility_tier': analysis['scores']['overall']['tier'],
        'market_presence': 'High' if analysis['scores']['overall']['score'] >= 80 else 'Medium' if analysis['scores']['overall']['score'] >= 60 else 'Low',
        'ai_discoverability': 'Strong' if analysis['scores']['authority']['score'] >= 75 else 'Moderate' if analysis['scores']['authority']['score'] >= 50 else 'Weak',
        'ranking_teaser': f"You are #{lb.get('state_rank', '?')} of {lb.get('state_total', '?')} in {agent['location']['state']}",
        'locked_sections': ['leaderboard', 'competitors', 'detailed_scores', 'geo_signals', 'action_plan']
    })

@app.route('/api/visibility/full', methods=['GET'])
def full_visibility():
    """Full visibility report - requires payment"""
    user = session.get('user', {})
    if not user.get('paid'):
        return jsonify({'error': 'Payment required', 'upgrade_required': True}), 403
    
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Agent name required'}), 400
    
    sys = get_system()
    result = sys.analyze_agent(name)
    
    if 'error' in result:
        return jsonify(result), 404
    
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
        const LockedSection = ({ title, children, onUnlock }) => (
            <div className="relative rounded-2xl border border-gray-200 bg-white p-6 overflow-hidden">
                <div className="blur-content">{children}</div>
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm">
                    <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 mb-3">
                        <LockIcon size={24}/>
                    </div>
                    <h4 className="font-semibold text-gray-900 mb-1">{title}</h4>
                    <p className="text-sm text-gray-500 mb-4">Unlock with full report</p>
                    <button onClick={onUnlock} className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition">
                        Unlock Now
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
        const SearchPage = ({ user, onSearch }) => {
            const [query, setQuery] = useState('');
            const [suggestions, setSuggestions] = useState([]);
            
            useEffect(() => {
                if (query.length > 2) {
                    fetch(`/api/search?q=${encodeURIComponent(query)}`)
                        .then(r => r.json())
                        .then(d => setSuggestions(d.results || []))
                        .catch(() => setSuggestions([]));
                } else {
                    setSuggestions([]);
                }
            }, [query]);
            
            return (
                <div className="min-h-screen">
                    {/* Hero Section */}
                    <div className="relative bg-gradient-to-br from-slate-900 to-slate-800 overflow-hidden">
                        <img src="https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1600" 
                            className="absolute inset-0 w-full h-full object-cover opacity-30"/>
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
                                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                                        </svg>
                                    </div>
                                    <input type="text" value={query} onChange={e => setQuery(e.target.value)}
                                        placeholder="Philadelphia, Rittenhouse, 19103..."
                                        className="flex-1 px-4 py-5 text-lg focus:outline-none"/>
                                    <button onClick={() => query && onSearch(query)}
                                        className="m-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition">
                                        Check Agent Visibility
                                    </button>
                                </div>
                                
                                {suggestions.length > 0 && (
                                    <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl shadow-xl border border-gray-100 overflow-hidden z-20">
                                        {suggestions.map(s => (
                                            <button key={s.id} onClick={() => onSearch(s.name)}
                                                className="w-full px-6 py-4 text-left hover:bg-gray-50 flex items-center gap-4 border-b border-gray-100 last:border-0">
                                                <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-semibold">
                                                    {s.name[0]}
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
            );
        };
        
        // Free Snapshot Page (blurred sections)
        const SnapshotPage = ({ agentName, user, onUpgrade, onBack }) => {
            const [data, setData] = useState(null);
            const [loading, setLoading] = useState(true);
            
            useEffect(() => {
                fetch(`/api/visibility/free?name=${encodeURIComponent(agentName)}`)
                    .then(r => r.json())
                    .then(d => { setData(d); setLoading(false); })
                    .catch(() => setLoading(false));
            }, [agentName]);
            
            if (loading) return (
                <div className="min-h-screen flex items-center justify-center">
                    <div className="text-center">
                        <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"/>
                        <p className="text-gray-600">Analyzing AI visibility...</p>
                    </div>
                </div>
            );
            
            if (!data || data.error) return (
                <div className="min-h-screen flex items-center justify-center">
                    <div className="text-center">
                        <p className="text-red-600 mb-4">{data?.error || 'Agent not found'}</p>
                        <button onClick={onBack} className="text-blue-600 hover:underline">← Back to search</button>
                    </div>
                </div>
            );
            
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
                            <div className="flex items-center gap-2">
                                <span className="text-sm text-gray-500">Logged in as</span>
                                <span className="font-medium text-gray-900">{user.name}</span>
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
                            
                            <LockedSection title="SALT Score Breakdown" onUnlock={onUpgrade}>
                                <div className="space-y-4">
                                    <div><div className="flex justify-between mb-1"><span>Semantic</span><span>--</span></div><div className="h-2 bg-gray-200 rounded-full"/></div>
                                    <div><div className="flex justify-between mb-1"><span>Authority</span><span>--</span></div><div className="h-2 bg-gray-200 rounded-full"/></div>
                                    <div><div className="flex justify-between mb-1"><span>Location</span><span>--</span></div><div className="h-2 bg-gray-200 rounded-full"/></div>
                                    <div><div className="flex justify-between mb-1"><span>Trust</span><span>--</span></div><div className="h-2 bg-gray-200 rounded-full"/></div>
                                </div>
                            </LockedSection>
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
            
            useEffect(() => {
                fetch(`/api/visibility/full?name=${encodeURIComponent(agentName)}`)
                    .then(r => r.json())
                    .then(d => { setData(d); setLoading(false); })
                    .catch(() => setLoading(false));
            }, [agentName]);
            
            if (loading) return (
                <div className="min-h-screen flex items-center justify-center">
                    <div className="text-center">
                        <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"/>
                        <p className="text-gray-600">Generating your full report...</p>
                    </div>
                </div>
            );
            
            if (!data || data.error) return (
                <div className="min-h-screen flex items-center justify-center">
                    <p className="text-red-600">{data?.error || 'Error loading report'}</p>
                </div>
            );
            
            const agent = data.agent;
            const analysis = data.analysis;
            const scores = analysis.scores;
            
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
                                    {agent.name.split(' ').map(n => n[0]).join('')}
                                </div>
                                <div className="flex-1 text-center lg:text-left">
                                    <p className="text-blue-200 text-sm mb-1">AI Visibility Report</p>
                                    <h1 className="text-3xl font-bold mb-2">{agent.name}</h1>
                                    <p className="text-blue-100">{agent.brokerage} • {agent.location?.city}, {agent.location?.state}</p>
                                </div>
                                <div className="text-center">
                                    <div className="text-5xl font-bold mb-1">{scores.overall.score}</div>
                                    <div className="text-blue-200">Overall Score</div>
                                    <div className="mt-2 px-4 py-1 bg-white/20 rounded-full text-sm">
                                        {scores.overall.tier} Tier
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
                            {analysis.geo_improvement_roadmap?.critical_issues && (
                                <div className="mb-8">
                                    <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                                        <span className="px-3 py-1 bg-red-100 text-red-700 rounded-full text-xs font-bold">CRITICAL</span>
                                        Address Immediately
                                    </h3>
                                    <ul className="space-y-2 border-l-4 border-red-500 pl-4">
                                        {analysis.geo_improvement_roadmap.critical_issues.map((item, i) => (
                                            <li key={i} className="text-sm text-gray-700">
                                                <span className="font-semibold text-red-600">{item.split(':')[0]}:</span> {item.split(':')[1]}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            
                            {/* High Priority */}
                            {analysis.geo_improvement_roadmap?.high_priority && (
                                <div className="mb-8">
                                    <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                                        <span className="px-3 py-1 bg-amber-100 text-amber-700 rounded-full text-xs font-bold">HIGH PRIORITY</span>
                                        3-6 Month Plan
                                    </h3>
                                    <div className="grid md:grid-cols-2 gap-4">
                                        {analysis.geo_improvement_roadmap.high_priority.map((item, i) => (
                                            <div key={i} className="bg-amber-50 rounded-lg p-4 border border-amber-200">
                                                <h4 className="font-semibold text-amber-900 text-sm mb-2">{item.split(':')[0]}</h4>
                                                <p className="text-sm text-amber-800">{item.split(':')[1] || item}</p>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            {/* Quick Wins */}
                            {analysis.geo_improvement_roadmap?.quick_wins && (
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
                                                <div className="text-sm text-emerald-900">{item}</div>
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
                                        {analysis.profile_analysis?.strengths?.map((s, i) => (
                                            <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                                                <span className="text-emerald-500">•</span> {s}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                                <div>
                                    <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                                        <span className="text-red-500">⚠</span> Critical Gaps
                                    </h3>
                                    <ul className="space-y-2">
                                        {analysis.profile_analysis?.areas_for_improvement?.map((a, i) => (
                                            <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                                                <span className="text-red-500">•</span> {a}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                            
                            {/* Detailed GEO Recommendations */}
                            <div className="space-y-4">
                                <h3 className="font-semibold text-gray-900 mb-4">Detailed GEO Improvement Strategy</h3>
                                {analysis.recommendations?.for_agent?.map((rec, i) => (
                                    <div key={i} className="bg-gradient-to-r from-blue-50 to-blue-100 rounded-lg p-5 border border-blue-200">
                                        <div className="flex items-start gap-3">
                                            <span className="inline-block w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold">
                                                {i + 1}
                                            </span>
                                            <p className="text-sm text-gray-800 leading-relaxed">{rec}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                        
                        {/* Executive Summary */}
                        <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-8 text-white">
                            <h2 className="text-xl font-bold mb-4">Executive Summary</h2>
                            <p className="text-gray-300 leading-relaxed">{analysis.executive_summary}</p>
                        </div>
                    </main>
                </div>
            );
        };
        
        // ============== MAIN APP ==============
        
        function App() {
            const [user, setUser] = useState(null);
            const [page, setPage] = useState('login'); // login, search, snapshot, paywall, report
            const [agentName, setAgentName] = useState('');
            
            // Check auth on mount
            useEffect(() => {
                fetch('/api/auth/status')
                    .then(r => r.json())
                    .then(d => {
                        if (d.logged_in) {
                            setUser(d);
                            setPage('search');
                        }
                    });
            }, []);
            
            const handleLogin = (userData) => {
                setUser(userData);
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
            
            // Render pages
            if (page === 'login') return <LoginPage onLogin={handleLogin}/>;
            if (page === 'search') return <SearchPage user={user} onSearch={handleSearch}/>;
            if (page === 'snapshot') return <SnapshotPage agentName={agentName} user={user} onUpgrade={handleUpgrade} onBack={() => setPage('search')}/>;
            if (page === 'paywall') return <PaywallPage agentName={agentName} user={user} onPaymentSuccess={handlePaymentSuccess} onBack={() => setPage('snapshot')}/>;
            if (page === 'report') return <FullReportPage agentName={agentName} user={user} onBack={() => setPage('search')}/>;
            
            return null;
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