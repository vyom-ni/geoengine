"""
Vieweo - AI Visibility Platform for Real Estate Agents
GEO (Generative Engine Optimization) Scoring System
Phase 1: Login → Free Snapshot → Paywall → Full Report
"""

from flask import Flask, jsonify, render_template, request, render_template_string, session, Response, send_from_directory
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
@app.route('/')
def index():
    return render_template("login.html")

@app.route('/dashboard')
def dashboard():
    return render_template("dashboard.html")

# Serve static images if they are in frontend/images
@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory('frontend/images', filename)

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