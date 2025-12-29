"""
Agent Intelligence System v2 - Flask API Server
Connects Python backend to React frontend
"""

from flask import Flask, jsonify, request, send_from_directory, render_template_string, Response
from flask_cors import CORS
import os
import json
import pandas as pd
from datetime import datetime
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# Import our agent intelligence system
from agent_intelligence_v2 import (
    AgentIntelligenceSystem,
    AgentDatabase,
    get_coordinates_from_zip
)

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for React frontend

# Configuration
class Config:
    EXCEL_PATH = os.environ.get('EXCEL_PATH', 'US_Real_Estate_Agents_Database.xlsx')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))
    HOST = os.environ.get('HOST', '0.0.0.0')

# Initialize the system
system = None

def get_system():
    global system
    if system is None:
        excel_path = Config.EXCEL_PATH
        if not os.path.exists(excel_path):
            # Try common locations
            possible_paths = [
                'US_Real_Estate_Agents_Database.xlsx',
                'data/US_Real_Estate_Agents_Database.xlsx',
                '../US_Real_Estate_Agents_Database.xlsx',
                'US_Real_Estate_Agents_Database__2_.xlsx',
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    excel_path = path
                    break
        
        system = AgentIntelligenceSystem(
            excel_path=excel_path,
            gemini_api_key=Config.GEMINI_API_KEY
        )
    return system


# ============== API ROUTES ==============

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'gemini_enabled': bool(Config.GEMINI_API_KEY),
        'version': '2.0.0'
    })


@app.route('/api/search', methods=['GET'])
def search_agents():
    """Search agents by name"""
    query = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 10))
    
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    try:
        sys = get_system()
        results = sys.db.search(query)[:limit]
        
        agents = []
        for record in results:
            agents.append({
                'id': record.get('Agent_ID', ''),
                'name': record.get('Full_Name', ''),
                'city': record.get('City', ''),
                'state': record.get('State', ''),
                'brokerage': record.get('Brokerage_Name', ''),
                'tier': record.get('Credibility_Tier', ''),
                'rating': record.get('Average_Rating', 0)
            })
        
        return jsonify({
            'query': query,
            'count': len(agents),
            'results': agents
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/agent/<agent_id>', methods=['GET'])
def get_agent_by_id(agent_id):
    """Get agent by ID"""
    try:
        sys = get_system()
        df = sys.db.df
        record = df[df['Agent_ID'] == agent_id]
        
        if record.empty:
            return jsonify({'error': f'Agent {agent_id} not found'}), 404
        
        profile = sys.db.record_to_profile(record.iloc[0].to_dict())
        analysis = sys.analyze_agent(profile.full_name)
        
        return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze', methods=['GET', 'POST'])
def analyze_agent():
    """Analyze agent by name - main endpoint"""
    if request.method == 'POST':
        data = request.get_json() or {}
        name = data.get('name', '')
        enrich = data.get('enrich', False)
    else:
        name = request.args.get('name', '').strip()
        enrich = request.args.get('enrich', 'false').lower() == 'true'
    
    if not name:
        return jsonify({'error': 'Agent name is required'}), 400
    
    try:
        sys = get_system()
        result = sys.analyze_agent(name, enrich_web=enrich)
        
        if 'error' in result:
            return jsonify(result), 404
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/map/agents', methods=['GET'])
def get_map_agents():
    """Get all agents for map display - returns ALL agents by default"""
    try:
        sys = get_system()
        
        # Optional filters
        state = request.args.get('state', '').upper()
        tier = request.args.get('tier', '')
        limit_param = request.args.get('limit', '')
        limit = int(limit_param) if limit_param else None  # No limit by default
        
        agents = sys.get_map_data()
        
        # Apply filters
        if state:
            agents = [a for a in agents if a.get('state', '').upper() == state]
        if tier:
            agents = [a for a in agents if a.get('tier', '').lower() == tier.lower()]
        
        # Only limit if explicitly requested
        if limit:
            agents = agents[:limit]
        
        return jsonify({
            'count': len(agents),
            'agents': agents
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    try:
        sys = get_system()
        df = sys.db.df
        
        stats = {
            'total_agents': len(df),
            'states': df['State'].nunique(),
            'cities': df['City'].nunique(),
            'avg_rating': round(df['Average_Rating'].mean(), 2),
            'avg_experience': round(df['Years_Experience'].mean(), 1),
            'tier_distribution': df['Credibility_Tier'].value_counts().to_dict(),
            'top_states': df['State'].value_counts().head(10).to_dict(),
            'specializations': df['Specialization'].value_counts().to_dict()
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/agents/top', methods=['GET'])
def get_top_agents():
    """Get top agents by various criteria"""
    try:
        sys = get_system()
        df = sys.db.df
        
        criteria = request.args.get('by', 'rating')
        limit = int(request.args.get('limit', 10))
        
        if criteria == 'rating':
            top = df.nlargest(limit, 'Average_Rating')
        elif criteria == 'reviews':
            top = df.nlargest(limit, 'Total_Reviews')
        elif criteria == 'experience':
            top = df.nlargest(limit, 'Years_Experience')
        elif criteria == 'followers':
            top = df.nlargest(limit, 'Follower_Count')
        else:
            top = df.nlargest(limit, 'Credibility_Score')
        
        agents = []
        for _, row in top.iterrows():
            agents.append({
                'id': row['Agent_ID'],
                'name': row['Full_Name'],
                'city': row['City'],
                'state': row['State'],
                'rating': row['Average_Rating'],
                'reviews': row['Total_Reviews'],
                'experience': row['Years_Experience'],
                'tier': row['Credibility_Tier'],
                'brokerage': row['Brokerage_Name']
            })
        
        return jsonify({
            'criteria': criteria,
            'count': len(agents),
            'agents': agents
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============== FRONTEND SERVING ==============

# Embedded HTML template with React frontend
FRONTEND_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Intelligence System</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { font-family: 'DM Sans', sans-serif; }
        .leaflet-container { font-family: 'DM Sans', sans-serif; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fadeIn { animation: fadeIn 0.5s ease-out; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .animate-pulse { animation: pulse 2s infinite; }
        .map-container { height: 400px; border-radius: 16px; overflow: hidden; }
    </style>
</head>
<body>
    <div id="root"></div>
    <script type="text/babel">
        const { useState, useEffect, useRef } = React;
        
        // API Base URL
        const API_BASE = '';
        
        // Score Ring Component
        const ScoreRing = ({ score, size = 120, color }) => {
            const radius = (size - 10) / 2;
            const circumference = 2 * Math.PI * radius;
            const offset = circumference - (score / 100) * circumference;
            
            return (
                <svg width={size} height={size} className="transform -rotate-90">
                    <circle cx={size/2} cy={size/2} r={radius} stroke="#f3f4f6" strokeWidth="10" fill="none" />
                    <circle cx={size/2} cy={size/2} r={radius} stroke={color} strokeWidth="10" fill="none"
                        strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset}
                        style={{ transition: 'stroke-dashoffset 1s ease-out' }} />
                </svg>
            );
        };
        
        // Grade Badge
        const GradeBadge = ({ grade }) => {
            const colors = {
                "A+": "bg-emerald-500", "A": "bg-emerald-400", "A-": "bg-green-400",
                "B+": "bg-lime-500", "B": "bg-yellow-400", "B-": "bg-amber-400",
                "C+": "bg-orange-400", "C": "bg-orange-500", "C-": "bg-red-400",
                "D": "bg-red-500", "F": "bg-red-600"
            };
            return (
                <span className={`${colors[grade] || 'bg-gray-400'} text-white px-3 py-1 rounded-lg font-bold text-sm`}>
                    {grade}
                </span>
            );
        };
        
        // Map Component with Leaflet
        const AgentMap = ({ agents, selectedAgent, onSelect, collapsed, onToggle }) => {
            const mapRef = useRef(null);
            const mapInstanceRef = useRef(null);
            const markersRef = useRef([]);
            
            useEffect(() => {
                if (collapsed || !mapRef.current) return;
                
                if (!mapInstanceRef.current) {
                    mapInstanceRef.current = L.map(mapRef.current).setView([39.8283, -98.5795], 4);
                    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                        attribution: '© OpenStreetMap contributors'
                    }).addTo(mapInstanceRef.current);
                }
                
                // Clear existing markers
                markersRef.current.forEach(m => m.remove());
                markersRef.current = [];
                
                // Add new markers
                agents.forEach(agent => {
                    if (agent.lat && agent.lng) {
                        const isSelected = selectedAgent?.name === agent.name;
                        const icon = L.divIcon({
                            className: 'custom-marker',
                            html: `<div style="
                                width: ${isSelected ? '20px' : '14px'};
                                height: ${isSelected ? '20px' : '14px'};
                                background: ${agent.tier === 'Elite' ? '#ea580c' : '#fdba74'};
                                border: 2px solid white;
                                border-radius: 50%;
                                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                            "></div>`,
                            iconSize: [isSelected ? 20 : 14, isSelected ? 20 : 14]
                        });
                        
                        const marker = L.marker([agent.lat, agent.lng], { icon })
                            .addTo(mapInstanceRef.current)
                            .bindPopup(`<b>${agent.name}</b><br>${agent.city}, ${agent.state}<br>Rating: ${agent.rating}/5`);
                        
                        marker.on('click', () => onSelect(agent));
                        markersRef.current.push(marker);
                    }
                });
                
                // Pan to selected agent
                if (selectedAgent?.lat && selectedAgent?.lng) {
                    mapInstanceRef.current.setView([selectedAgent.lat, selectedAgent.lng], 8);
                }
                
            }, [agents, selectedAgent, collapsed]);
            
            return (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                    <button onClick={onToggle}
                        className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
                        <div className="flex items-center gap-3">
                            <span className="text-orange-500">🗺️</span>
                            <span className="font-semibold text-gray-800">Agent Locations Map</span>
                            <span className="text-sm text-gray-500">({agents.length} agents)</span>
                        </div>
                        <svg className={`w-5 h-5 text-gray-400 transition-transform ${collapsed ? '' : 'rotate-180'}`} 
                            fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                    </button>
                    {!collapsed && (
                        <div className="p-4 pt-0">
                            <div ref={mapRef} className="map-container" />
                            <div className="flex items-center justify-center gap-6 mt-4 text-sm">
                                <div className="flex items-center gap-2">
                                    <span className="w-3 h-3 rounded-full bg-orange-600" />
                                    <span className="text-gray-600">Elite Agents</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="w-3 h-3 rounded-full bg-orange-300" />
                                    <span className="text-gray-600">Other Tiers</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            );
        };
        
        // Score Card Component
        const ScoreCard = ({ title, icon, data, color }) => {
            const [expanded, setExpanded] = useState(false);
            
            return (
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                    <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <span className="text-2xl">{icon}</span>
                            <h3 className="font-semibold text-gray-800">{title}</h3>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-2xl font-bold" style={{ color }}>{data.score}</span>
                            <GradeBadge grade={data.grade} />
                        </div>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-1000" 
                            style={{ width: `${data.score}%`, backgroundColor: color }} />
                    </div>
                    <button onClick={() => setExpanded(!expanded)} 
                        className="mt-3 text-sm text-orange-600 hover:text-orange-700 font-medium">
                        {expanded ? '▲ Hide factors' : '▼ View factors'}
                    </button>
                    {expanded && (
                        <ul className="mt-3 space-y-2">
                            {data.factors?.map((f, i) => (
                                <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                                    <span className="text-emerald-500">✓</span> {f}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            );
        };
        
        // Main App
        function App() {
            const [searchQuery, setSearchQuery] = useState('');
            const [suggestions, setSuggestions] = useState([]);
            const [agentData, setAgentData] = useState(null);
            const [mapAgents, setMapAgents] = useState([]);
            const [loading, setLoading] = useState(false);
            const [mapCollapsed, setMapCollapsed] = useState(false);
            const [selectedMapAgent, setSelectedMapAgent] = useState(null);
            const [stats, setStats] = useState(null);
            
            // Load map agents and stats on mount
            useEffect(() => {
                fetch(`${API_BASE}/api/map/agents`)
                    .then(r => r.json())
                    .then(data => setMapAgents(data.agents || []))
                    .catch(console.error);
                    
                fetch(`${API_BASE}/api/stats`)
                    .then(r => r.json())
                    .then(setStats)
                    .catch(console.error);
            }, []);
            
            // Search suggestions
            useEffect(() => {
                if (searchQuery.length > 1) {
                    fetch(`${API_BASE}/api/search?q=${encodeURIComponent(searchQuery)}&limit=5`)
                        .then(r => r.json())
                        .then(data => setSuggestions(data.results || []))
                        .catch(() => setSuggestions([]));
                } else {
                    setSuggestions([]);
                }
            }, [searchQuery]);
            
            const handleSearch = (name) => {
                if (!name) return;
                setLoading(true);
                setSuggestions([]);
                
                fetch(`${API_BASE}/api/analyze?name=${encodeURIComponent(name)}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.error) {
                            alert(data.error);
                            setAgentData(null);
                        } else {
                            setAgentData(data);
                            if (data.agent?.location?.coordinates) {
                                setSelectedMapAgent({
                                    name: data.agent.name,
                                    lat: data.agent.location.coordinates.lat,
                                    lng: data.agent.location.coordinates.lng
                                });
                            }
                        }
                    })
                    .catch(err => alert('Error: ' + err.message))
                    .finally(() => setLoading(false));
            };
            
            const handleMapSelect = (agent) => {
                setSelectedMapAgent(agent);
                setSearchQuery(agent.name);
                handleSearch(agent.name);
            };
            
            return (
                <div className="min-h-screen bg-gradient-to-br from-orange-50 via-white to-amber-50">
                    {/* Header */}
                    <header className="border-b border-orange-100 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
                        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 bg-gradient-to-br from-orange-500 to-amber-500 rounded-xl flex items-center justify-center text-white font-bold">
                                    AI
                                </div>
                                <div>
                                    <h1 className="text-xl font-bold text-gray-900">Agent Intelligence</h1>
                                    <p className="text-xs text-gray-500">Powered by Gemini AI</p>
                                </div>
                            </div>
                            {stats && (
                                <div className="flex items-center gap-2 text-sm text-gray-500">
                                    <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                                    <span>{stats.total_agents?.toLocaleString()} agents indexed</span>
                                </div>
                            )}
                        </div>
                    </header>
                    
                    <main className="max-w-7xl mx-auto px-6 py-8">
                        {/* Search */}
                        <div className="max-w-2xl mx-auto mb-8">
                            <div className="text-center mb-6">
                                <h2 className="text-3xl font-bold text-gray-900 mb-2">Find Any Agent</h2>
                                <p className="text-gray-600">Enter an agent's name for AI-powered analysis</p>
                            </div>
                            <div className="relative">
                                <input type="text" value={searchQuery} 
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleSearch(searchQuery)}
                                    placeholder="Search by agent name..."
                                    className="w-full px-6 py-4 bg-white border-2 border-gray-200 rounded-2xl text-lg focus:outline-none focus:border-orange-400" />
                                <button onClick={() => handleSearch(searchQuery)} disabled={loading}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 px-6 py-3 bg-gradient-to-r from-orange-500 to-amber-500 text-white rounded-xl font-semibold hover:opacity-90 disabled:opacity-50">
                                    {loading ? 'Analyzing...' : 'Analyze'}
                                </button>
                                {suggestions.length > 0 && (
                                    <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-200 rounded-xl shadow-xl z-10 overflow-hidden">
                                        {suggestions.map(s => (
                                            <button key={s.id} onClick={() => { setSearchQuery(s.name); handleSearch(s.name); }}
                                                className="w-full px-5 py-3 text-left hover:bg-orange-50 flex items-center gap-3">
                                                <span className="w-10 h-10 bg-orange-100 text-orange-600 rounded-full flex items-center justify-center font-semibold">
                                                    {s.name[0]}
                                                </span>
                                                <div>
                                                    <div className="font-medium text-gray-800">{s.name}</div>
                                                    <div className="text-sm text-gray-500">{s.city}, {s.state} • {s.brokerage}</div>
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                        
                        {/* Map */}
                        <div className="mb-8">
                            <AgentMap agents={mapAgents} selectedAgent={selectedMapAgent} 
                                onSelect={handleMapSelect} collapsed={mapCollapsed} 
                                onToggle={() => setMapCollapsed(!mapCollapsed)} />
                        </div>
                        
                        {/* Results */}
                        {agentData && (
                            <div className="space-y-6 animate-fadeIn">
                                {/* Agent Card */}
                                <div className="bg-white rounded-3xl p-8 shadow-sm border border-gray-100">
                                    <div className="flex flex-col lg:flex-row gap-8">
                                        <div className="flex flex-col items-center lg:items-start gap-4">
                                            <div className="relative">
                                                <div className="w-32 h-32 rounded-2xl bg-gradient-to-br from-orange-400 to-amber-400 flex items-center justify-center text-white text-4xl font-bold shadow-lg">
                                                    {agentData.agent.name.split(' ').map(n => n[0]).join('')}
                                                </div>
                                                {agentData.agent.credibility?.realtrends_verified && (
                                                    <div className="absolute -bottom-2 -right-2 w-8 h-8 bg-emerald-500 rounded-full flex items-center justify-center text-white shadow-lg">✓</div>
                                                )}
                                            </div>
                                            <div className="text-center lg:text-left">
                                                <h2 className="text-2xl font-bold text-gray-900">{agentData.agent.name}</h2>
                                                <p className="text-orange-600 font-medium">{agentData.agent.brokerage}</p>
                                                <p className="text-gray-500 text-sm">{agentData.agent.location?.city}, {agentData.agent.location?.state}</p>
                                            </div>
                                        </div>
                                        
                                        <div className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-4">
                                            <div className="bg-orange-50 rounded-xl p-4 text-center">
                                                <div className="text-2xl font-bold text-orange-600">{agentData.agent.experience?.years || 0}</div>
                                                <div className="text-sm text-gray-600">Years Exp.</div>
                                            </div>
                                            <div className="bg-amber-50 rounded-xl p-4 text-center">
                                                <div className="text-2xl font-bold text-amber-600">{agentData.agent.experience?.career_sales || 'N/A'}</div>
                                                <div className="text-sm text-gray-600">Career Sales</div>
                                            </div>
                                            <div className="bg-emerald-50 rounded-xl p-4 text-center">
                                                <div className="text-2xl font-bold text-emerald-600">{agentData.agent.reviews?.average_rating || 0}</div>
                                                <div className="text-sm text-gray-600">Avg Rating</div>
                                            </div>
                                            <div className="bg-blue-50 rounded-xl p-4 text-center">
                                                <div className="text-2xl font-bold text-blue-600">{agentData.agent.reviews?.total_count || 0}</div>
                                                <div className="text-sm text-gray-600">Reviews</div>
                                            </div>
                                        </div>
                                        
                                        <div className="flex flex-col items-center justify-center">
                                            <div className="relative">
                                                <ScoreRing score={agentData.analysis?.scores?.overall?.score || 0} size={140} color="#f97316" />
                                                <div className="absolute inset-0 flex flex-col items-center justify-center">
                                                    <span className="text-3xl font-bold text-gray-900">{agentData.analysis?.scores?.overall?.score || 0}</span>
                                                    <span className="text-xs text-gray-500">Overall</span>
                                                </div>
                                            </div>
                                            <div className="mt-3 flex items-center gap-2">
                                                <GradeBadge grade={agentData.analysis?.scores?.overall?.grade || 'N/A'} />
                                                <span className="px-3 py-1 bg-orange-100 text-orange-700 rounded-full text-sm font-semibold">
                                                    {agentData.analysis?.scores?.overall?.tier || 'Unknown'}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    {agentData.agent.bio && (
                                        <div className="mt-6 pt-6 border-t border-gray-100">
                                            <p className="text-gray-700">{agentData.agent.bio}</p>
                                        </div>
                                    )}
                                </div>
                                
                                {/* Score Cards */}
                                {agentData.analysis?.scores && (
                                    <div className="grid md:grid-cols-2 gap-6">
                                        <ScoreCard title="Authority Score" icon="🏆" data={agentData.analysis.scores.authority} color="#f97316" />
                                        <ScoreCard title="Sentiment Score" icon="💬" data={agentData.analysis.scores.sentiment} color="#8b5cf6" />
                                        <ScoreCard title="Trustworthiness" icon="🛡️" data={agentData.analysis.scores.trustworthiness} color="#10b981" />
                                        <ScoreCard title="Location Visibility" icon="📍" data={agentData.analysis.scores.location_visibility} color="#3b82f6" />
                                    </div>
                                )}
                                
                                {/* Executive Summary */}
                                {agentData.analysis?.executive_summary && (
                                    <div className="bg-gradient-to-r from-orange-500 to-amber-500 rounded-3xl p-8 text-white">
                                        <h3 className="text-xl font-bold mb-4">📋 Executive Summary</h3>
                                        <p className="text-lg leading-relaxed opacity-95">{agentData.analysis.executive_summary}</p>
                                    </div>
                                )}
                            </div>
                        )}
                        
                        {/* Empty State */}
                        {!agentData && !loading && (
                            <div className="text-center py-16">
                                <div className="w-24 h-24 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-6 text-4xl">
                                    🔍
                                </div>
                                <h3 className="text-xl font-semibold text-gray-800 mb-2">Search for an Agent</h3>
                                <p className="text-gray-500">Enter a name above or click on the map to explore</p>
                            </div>
                        )}
                    </main>
                </div>
            );
        }
        
        ReactDOM.createRoot(document.getElementById('root')).render(<App />);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Serve the React frontend"""
    return Response(FRONTEND_HTML, mimetype='text/html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory(app.static_folder, filename)


# ============== ERROR HANDLERS ==============

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# ============== MAIN ==============

def run_server():
    """Run the Flask server"""
    print(f"""
============================================================
       AGENT INTELLIGENCE SYSTEM v2.0
       Powered by Gemini AI
============================================================
Server running at: http://localhost:{Config.PORT}
API docs at: http://localhost:{Config.PORT}/api/health

Gemini API: {'✓ Enabled' if Config.GEMINI_API_KEY else '✗ Disabled (using fallback)'}
============================================================
    """)
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )


if __name__ == '__main__':
    run_server()