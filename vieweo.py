#!/usr/bin/env python3
"""
Vieweo - AI Visibility Platform for Real Estate Agents
Production-Ready Version with Modern UI
"""

import os
import sys
import traceback
import threading
import gc
from functools import lru_cache
from dotenv import load_dotenv
load_dotenv()  # Load .env file

from flask import Flask, request, jsonify, session
from agent_intelligence_v2 import AgentIntelligenceSystem

# Flask Setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'vieweo-secret-key-change-in-production')
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size

# Thread-safe lock for system initialization
_system_lock = threading.Lock()

@app.errorhandler(Exception)
def handle_exception(e):
    """Global error handler that prints traceback"""
    traceback.print_exc()
    return jsonify({'error': str(e), 'type': type(e).__name__}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/favicon.ico')
def favicon():
    return '', 204  # No content

@app.route('/images/<path:filename>')
def serve_images(filename):
    """Serve images from the images folder"""
    import os
    from flask import send_from_directory
    images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images')
    return send_from_directory(images_dir, filename)

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    global system
    return jsonify({
        'status': 'healthy',
        'system_loaded': system is not None,
        'agents_count': len(system.db.df) if system else 0
    })

# Configuration
class Config:
    EXCEL_PATH = os.environ.get('EXCEL_PATH', 'US_Real_Estate_Agents_Database.xlsx')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))

system = None
_system_loading = False

# In-memory cache for agent analysis results (avoids session cookie overflow)
# Format: {agent_name_lower: {'data': result, 'timestamp': time}}
_agent_cache = {}
_cache_ttl = 300  # 5 minutes TTL

def get_cached_agent(name):
    """Get cached agent data if available and not expired"""
    import time
    key = name.lower().strip()
    if key in _agent_cache:
        entry = _agent_cache[key]
        if time.time() - entry['timestamp'] < _cache_ttl:
            return entry['data']
        else:
            del _agent_cache[key]
    return None

def set_cached_agent(name, data):
    """Cache agent data with timestamp"""
    import time
    key = name.lower().strip()
    _agent_cache[key] = {'data': data, 'timestamp': time.time()}

def get_system(force_reload=False):
    """Get or initialize the global system instance (thread-safe singleton)"""
    global system, _system_loading

    # Return existing system if already loaded
    if system is not None and not force_reload:
        return system

    with _system_lock:
        # Double-check after acquiring lock
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
            system = AgentIntelligenceSystem(
                excel_path, 
                gemini_api_key=Config.GEMINI_API_KEY,
                openai_api_key=Config.OPENAI_API_KEY
            )
            print(f"{'='*60}")
            print(f"✅ SYSTEM READY - {len(system.db.df)} agents loaded")
            print(f"{'='*60}\n")
            
            # Force garbage collection after heavy initialization
            gc.collect()
            
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

    # Format results - ensure all fields are present including brokerage
    formatted_results = []
    for r in results:
        formatted_results.append({
            'id': r.get('id', ''),
            'name': r.get('name', ''),
            'city': r.get('city', ''),
            'state': r.get('state', ''),
            'brokerage': r.get('brokerage', '')
        })

    return jsonify({
        'count': len(formatted_results),
        'results': formatted_results
    })

@app.route('/api/visibility/free', methods=['GET'])
def free_visibility():
    """Basic agent details - no login required. SALT scores require login.
    Uses in-memory cache to avoid session cookie overflow."""
    name = request.args.get('name', '').strip()
    print(f"\n🔍 Visibility request for: '{name}'")

    if not name:
        return jsonify({'error': 'Agent name required'}), 400

    # Get user status first
    user = session.get('user', {})
    is_logged_in = bool(user) and user.get('logged_in', False)
    is_admin = user.get('is_admin', False)

    # Check in-memory cache first (avoids cookie overflow issues)
    result = get_cached_agent(name)
    
    if result:
        print(f"✅ Using cached analysis for: {name}")
    else:
        # No cache - fetch and analyze
        try:
            sys = get_system()
            result = sys.analyze_agent(name)
            print(f"✅ Analysis complete for: {name}")

            # Cache in memory (not in session to avoid cookie overflow)
            if 'error' not in result:
                set_cached_agent(name, result)
        except Exception as e:
            print(f"❌ Error analyzing agent: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

    if 'error' in result:
        print(f"❌ Agent not found: {name}")
        return jsonify({'error': result['error'], 'not_found': True}), 404

    # Extract data from cached/fresh result
    agent = result['agent']
    analysis = result['analysis']
    lb = result.get('leaderboard_context', {})

    # Safe score access - ensure we get numeric values
    scores = analysis.get('scores', {})
    overall_score = int(scores.get('overall', {}).get('score', 0) or 0)
    semantic_score = int(scores.get('semantic', {}).get('score', 0) or 0)
    authority_score = int(scores.get('authority', {}).get('score', 0) or 0)
    location_score = int(scores.get('location', {}).get('score', 0) or 0)
    trust_score = int(scores.get('trust', {}).get('score', 0) or 0)

    # Debug log the scores
    print(f"📊 SALT Scores - S:{semantic_score} A:{authority_score} L:{location_score} T:{trust_score} Overall:{overall_score}")

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
        'visibility_grade': scores.get('overall', {}).get('grade', 'N/A'),
        'visibility_tier': scores.get('overall', {}).get('tier', 'Unknown'),

        # TIER 2: Requires login (SALT scores)
        'salt_scores': {
            'semantic': semantic_score,
            'authority': authority_score,
            'location': location_score,
            'trust': trust_score
        } if is_logged_in or is_admin else None,

        # LLM Visibility Scores (requires login)
        'llm_visibility_scores': analysis.get('llm_visibility_scores', {
            'chatgpt': 0,
            'perplexity': 0,
            'claude': 0,
            'gemini': 0
        }) if is_logged_in or is_admin else None,

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

    print(f"✅ Returning data: score={overall_score}")
    return jsonify(response_data)

@app.route('/api/visibility/full', methods=['GET'])
def full_visibility():
    """Full visibility report - requires payment.
    Uses in-memory cache to avoid session cookie overflow."""
    user = session.get('user', {})
    if not user.get('paid'):
        return jsonify({'error': 'Payment required', 'upgrade_required': True}), 403

    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Agent name required'}), 400

    # Check in-memory cache first
    result = get_cached_agent(name)
    
    if result:
        print(f"✅ Using cached full report for: {name}")
        return jsonify(result)

    # Not in cache - analyze and cache
    sys = get_system()
    result = sys.analyze_agent(name)

    if 'error' in result:
        return jsonify(result), 404

    # Cache in memory (not session to avoid cookie overflow)
    set_cached_agent(name, result)
    print(f"✅ Analyzed and cached full report for: {name}")

    return jsonify(result)

    return jsonify(result)

@app.route('/api/agents/add', methods=['POST'])
def add_agent():
    """Add a new agent to the database with duplicate prevention"""
    data = request.get_json() or {}

    # Validate required fields
    required_fields = ['full_name', 'city', 'state', 'phone']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    try:
        import pandas as pd

        sys = get_system()

        # Check for duplicates - by name and city/state combination
        full_name = data['full_name'].strip()
        city = data['city'].strip()
        state = data['state'].strip().upper()
        phone = data['phone'].strip()

        # Normalize for comparison
        name_lower = full_name.lower()
        city_lower = city.lower()

        # Check if agent already exists (same name + location OR same phone)
        # Normalize phone for comparison
        phone_digits = ''.join(filter(str.isdigit, phone))

        # Build duplicate check conditions
        name_location_match = (
            (sys.db.df['Full_Name'].str.lower().str.strip() == name_lower) &
            (sys.db.df['City'].str.lower().str.strip() == city_lower) &
            (sys.db.df['State'].str.upper().str.strip() == state)
        )

        # Check phone match only if Phone_Number column exists and has data
        if 'Phone_Number' in sys.db.df.columns and phone_digits:
            phone_match = sys.db.df['Phone_Number'].fillna('').astype(str).str.replace(r'[^\d]', '', regex=True) == phone_digits
            existing = sys.db.df[name_location_match | phone_match]
        else:
            existing = sys.db.df[name_location_match]

        if len(existing) > 0:
            existing_agent = existing.iloc[0]
            return jsonify({
                'error': f'Agent already exists: {existing_agent["Full_Name"]} in {existing_agent["City"]}, {existing_agent["State"]}',
                'duplicate': True,
                'existing_agent': existing_agent['Full_Name']
            }), 409

        # Generate unique Agent_ID
        max_id = sys.db.df['Agent_ID'].astype(str).str.extract(r'(\d+)').astype(int).max()[0]
        new_id = f"AG{max_id + 1:06d}"

        # Prepare new agent row with correct column names from database
        new_agent = {
            'Agent_ID': new_id,
            'Full_Name': full_name,
            'City': city,
            'State': state,
            'Phone_Number': phone,
            'Brokerage_Name': data.get('brokerage', '').strip(),
            'Website_Links': data.get('website', '').strip(),
            'Years_Experience': int(data.get('years_experience', 0) or 0),
            'Specialization': data.get('specialization', '').strip(),
            'Average_Rating': 0,
            'Total_Reviews': 0,
            'Credibility_Score': 0
        }

        # Add to DataFrame
        sys.db.df = pd.concat([sys.db.df, pd.DataFrame([new_agent])], ignore_index=True)

        # Update the name_lower column for the new agent (required for search indexing)
        sys.db.df['name_lower'] = sys.db.df['Full_Name'].str.lower().str.strip()

        # Save to Excel - try original file first, then backup if locked
        excel_path = Config.EXCEL_PATH
        # Get columns to save (exclude internal computed columns)
        save_columns = [col for col in sys.db.df.columns if col not in ['name_lower', 'rating_rank', 'review_rank', 'experience_rank', 'credibility_rank']]
        
        saved = False
        save_message = ""
        
        # First, check if the file can be opened for writing
        def is_file_locked(filepath):
            if not os.path.exists(filepath):
                return False
            try:
                with open(filepath, 'a'):
                    pass
                return False
            except (IOError, PermissionError):
                return True
        
        if is_file_locked(excel_path):
            # File is locked - save to a backup file instead
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = excel_path.replace('.xlsx', f'_backup_{timestamp}.xlsx')
            
            try:
                sys.db.df[save_columns].to_excel(backup_path, index=False)
                print(f"⚠️ Original file locked. Saved to backup: {backup_path}")
                saved = True
                save_message = f"Agent added! Note: The main database file was locked (possibly open in Excel). Data was saved to backup file: {os.path.basename(backup_path)}. Please close Excel and merge the backup file."
            except Exception as e:
                print(f"❌ Could not save to backup either: {e}")
                raise Exception(f"Could not save agent. Please close Excel and try again: {str(e)}")
        else:
            # File is not locked - save directly
            try:
                sys.db.df[save_columns].to_excel(excel_path, index=False)
                print(f"✅ Saved to Excel: {excel_path} (total agents: {len(sys.db.df)})")
                saved = True
                save_message = f'Agent "{new_agent["Full_Name"]}" added successfully!'
            except Exception as e:
                print(f"❌ Error saving to Excel: {e}")
                raise Exception(f"Could not save agent: {str(e)}")
        
        if not saved:
            raise Exception("Failed to save agent to database")

        # Rebuild search cache
        sys.db._build_search_cache()
        print(f"🔍 Search cache rebuilt with {len(sys.db.search_index)} keys")

        print(f"✅ Added new agent: {new_agent['Full_Name']} (ID: {new_id})")

        return jsonify({
            'success': True,
            'agent_id': new_id,
            'agent_name': new_agent['Full_Name'],
            'message': save_message + ' Please refresh the page to see them in search suggestions.',
            'refresh_required': True
        })

    except Exception as e:
        print(f"❌ Error adding agent: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to add agent: {str(e)}'}), 500

# ============== FRONTEND ==============

@app.route('/test')
def test_route():
    """Simple test route to verify server is working"""
    return "Server is working!"

@app.route('/')
def index():
    try:
        return FRONTEND_HTML
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500

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
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideIn { from { transform: translateX(-100%); } to { transform: translateX(0); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        .animate-in { animation: fadeIn 0.5s ease-out forwards; }
        .animate-slide { animation: slideIn 0.4s ease-out forwards; }
        .animate-float { animation: float 3s ease-in-out infinite; }
        
        /* Zillow-inspired color scheme */
        :root {
            --primary: #006AFF;
            --primary-dark: #0051CC;
            --secondary: #1E3A5F;
            --accent: #00D395;
            --warning: #FF9500;
            --error: #FF3B30;
        }
        
        .text-primary { color: var(--primary); }
        .bg-primary { background-color: var(--primary); }
        .border-primary { border-color: var(--primary); }
        
        .glass-effect {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
        }
        
        /* Score bars with real estate colors */
        .score-bar-semantic { background: linear-gradient(90deg, #006AFF, #0051CC); }
        .score-bar-authority { background: linear-gradient(90deg, #8B5CF6, #7C3AED); }
        .score-bar-location { background: linear-gradient(90deg, #00D395, #10B981); }
        .score-bar-trust { background: linear-gradient(90deg, #FF9500, #F59E0B); }
        
        /* Radial chart for scores */
        .score-ring {
            background: conic-gradient(var(--primary) calc(var(--score) * 1%), #e5e7eb 0);
            border-radius: 50%;
        }
        
        /* Real estate card shadows */
        .card-shadow {
            box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.05);
        }
        .card-shadow-lg {
            box-shadow: 0 4px 6px rgba(0,0,0,0.07), 0 10px 40px rgba(0,0,0,0.1);
        }
        
        /* Hover effects */
        .hover-lift { transition: transform 0.2s, box-shadow 0.2s; }
        .hover-lift:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.12); }
    </style>
</head>
<body class="bg-gray-50">
    <div id="root"></div>

    <script type="text/babel">
        const { useState, useEffect, useRef, useCallback } = React;

        // ============== AI PLATFORM LOGOS (Official Brand Colors) ==============
        const AILogos = {
            chatgpt: 'https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg',
            perplexity: 'https://uxwing.com/wp-content/themes/uxwing/download/brands-and-social-media/perplexity-ai-icon.png',
            claude: 'https://upload.wikimedia.org/wikipedia/commons/8/8a/Claude_AI_logo.svg',
            gemini: 'https://upload.wikimedia.org/wikipedia/commons/8/8a/Google_Gemini_logo.svg'
        };

        // ============== REAL ESTATE IMAGES ==============
        const RealEstateImages = {
            hero: 'https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=1920&q=80',
            luxury: 'https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=800&q=80',
            suburban: 'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&q=80',
            modern: 'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800&q=80',
            agent: 'https://images.unsplash.com/photo-1560250097-0b93528c311a?w=400&q=80',
            office: 'https://images.unsplash.com/photo-1497366216548-37526070297c?w=1200&q=80',
            neighborhood: 'https://images.unsplash.com/photo-1448630360428-65456885c650?w=1200&q=80',
            sold: 'https://images.unsplash.com/photo-1582407947304-fd86f028f716?w=800&q=80'
        };

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

                        <p className="text-slate-500 text-xs mt-6 animate-pulse">Powered by Vieweo</p>
                    </div>
                </div>
            );
        };

        // ============== FOOTER SECTION WITH IMAGE ==============
        const FooterSection = () => {
            return (
                <>
                    {/* Industry News Section */}
                    <div className="bg-gray-50 py-16">
                        <div className="max-w-4xl mx-auto px-6">
                            <h2 className="text-2xl font-bold text-gray-900 mb-3 text-center">AI is Transforming Real Estate</h2>
                            <p className="text-gray-600 text-center mb-8">Stay ahead of the curve with the latest industry insights</p>
                            <div className="bg-white rounded-xl shadow-lg overflow-hidden hover-lift">
                                <img
                                    src="/images/Section.png"
                                    alt="Survey: 82% of Americans Use AI for Housing Market Information"
                                    className="w-full h-auto"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Footer */}
                    <footer className="bg-gray-900 text-white py-12">
                        <div className="max-w-6xl mx-auto px-6">
                            <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                                <div className="flex items-center gap-2">
                                    <img src="/images/ViewoLogo.PNG" alt="Vieweo" className="h-8 w-auto" />
                                </div>
                                <p className="text-gray-400 text-sm">© 2026 Vieweo. AI Visibility Platform for Real Estate Professionals.</p>
                            </div>
                        </div>
                    </footer>
                </>
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
            const [successData, setSuccessData] = useState(null);

            if (!show) return null;

            const handleSubmit = async (e) => {
                e.preventDefault();
                setLoading(true);
                setError('');
                setSuccessData(null);

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
                        setSuccessData(result);
                    } else {
                        setError(result.error || 'Failed to add agent');
                    }
                } catch (err) {
                    setError('Network error. Please try again.');
                } finally {
                    setLoading(false);
                }
            };

            const handleRefreshPage = () => {
                window.location.reload();
            };

            const handleClose = () => {
                setSuccessData(null);
                setError('');
                onClose();
            };

            // Success state UI
            if (successData) {
                return (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
                        <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-8 my-8 relative animate-in text-center">
                            <div className="w-20 h-20 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-full flex items-center justify-center mx-auto mb-6">
                                <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                                </svg>
                            </div>
                            <h3 className="text-2xl font-bold text-gray-900 mb-2">Agent Added Successfully!</h3>
                            <p className="text-gray-600 mb-2">{successData.agent_name} has been added to the database.</p>
                            <p className="text-sm text-gray-500 mb-6">Please refresh the page to see the new agent in search suggestions.</p>
                            <div className="space-y-3">
                                <button
                                    onClick={handleRefreshPage}
                                    className="w-full py-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-semibold rounded-xl hover:from-emerald-700 hover:to-teal-700 transition shadow-lg shadow-emerald-500/30"
                                >
                                    Refresh Page Now
                                </button>
                                <button
                                    onClick={handleClose}
                                    className="w-full py-3 bg-gray-100 text-gray-700 font-semibold rounded-xl hover:bg-gray-200 transition"
                                >
                                    Close
                                </button>
                            </div>
                        </div>
                    </div>
                );
            }

            return (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
                    <div className="bg-white rounded-3xl shadow-2xl max-w-2xl w-full p-8 my-8 relative animate-in">
                        <button
                            onClick={handleClose}
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
                            <p className="text-sm text-gray-500">Register a new agent to access AI Visibility scores</p>
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
            <nav className="bg-white border-b border-gray-200 sticky top-0 z-40 card-shadow">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="flex items-center justify-between h-16">
                        {/* Logo */}
                        <div className="flex items-center gap-8">
                            <div className="flex items-center gap-2">
                                <img src="/images/ViewoLogo.PNG" alt="Vieweo" className="h-8 w-auto" />
                            </div>
                            
                            {/* Nav Links */}
                            <div className="hidden md:flex items-center gap-6">
                                <a href="#" className="text-sm font-medium text-gray-600 hover:text-[#006AFF] transition">For Agents</a>
                                <a href="#" className="text-sm font-medium text-gray-600 hover:text-[#006AFF] transition">Pricing</a>
                                <a href="#" className="text-sm font-medium text-gray-600 hover:text-[#006AFF] transition">Resources</a>
                            </div>
                        </div>

                        {/* Right Side */}
                        <div className="flex items-center gap-3">
                            <button
                                onClick={onAddAgent}
                                className="hidden sm:flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 hover:text-[#006AFF] hover:bg-blue-50 rounded-lg transition"
                            >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"/>
                                </svg>
                                Add Agent
                            </button>

                            {user ? (
                                <div className="flex items-center gap-3">
                                    {user.is_admin && (
                                        <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs font-semibold rounded">
                                            ADMIN
                                        </span>
                                    )}
                                    <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-full">
                                        <div className="w-6 h-6 bg-[#006AFF] rounded-full flex items-center justify-center text-white text-xs font-bold">
                                            {user.name?.[0] || 'U'}
                                        </div>
                                        <span className="text-sm font-medium text-gray-700">{user.name?.split(' ')[0]}</span>
                                    </div>
                                    <button
                                        onClick={onLogout}
                                        className="text-sm font-medium text-gray-500 hover:text-gray-700 transition"
                                    >
                                        Logout
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={onLogin}
                                    className="px-5 py-2 bg-[#006AFF] text-white text-sm font-semibold rounded-lg hover:bg-[#0051CC] transition"
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
                <div className="min-h-screen bg-gray-50">
                    <Navbar user={user} onLogin={onLogin} onLogout={onLogout} onAddAgent={onAddAgent} />

                    {/* Hero Section - Zillow Style */}
                    <div className="relative pb-16">
                        {/* Background with overlay */}
                        <div className="absolute inset-0 overflow-hidden">
                            <img
                                src={RealEstateImages.hero}
                                alt="Luxury real estate"
                                className="w-full h-full object-cover"
                            />
                            <div className="absolute inset-0 bg-gradient-to-r from-[#1E3A5F]/95 via-[#1E3A5F]/80 to-transparent"/>
                        </div>

                        <div className="relative z-20 max-w-7xl mx-auto px-6 py-20 lg:py-28">
                            <div className="max-w-2xl">
                                <span className="inline-block px-3 py-1 bg-[#00D395]/20 text-[#00D395] text-sm font-semibold rounded-full mb-4">
                                    Proprietary AI visibility engine
                                </span>
                                <h1 className="text-4xl lg:text-5xl font-bold text-white mb-4 leading-tight">
                                    Real Estate you sell<br/>
                                    <span className="text-[#006AFF]">AI visibility you own</span>
                                </h1>
                                <p className="text-lg text-gray-300 mb-8">
                                    See how visible you are on <b>AI Search</b>.
                                    Optimize your digital presence to capture more leads.
                                </p>

                                {/* Search Box - Clean Zillow Style */}
                                <div className="relative z-30">
                                    <div className="bg-white rounded-lg shadow-xl overflow-hidden">
                                        <div className="flex items-center">
                                            <div className="pl-4 text-gray-400">
                                                {loading ? (
                                                    <div className="w-5 h-5 border-2 border-[#006AFF] border-t-transparent rounded-full animate-spin"/>
                                                ) : (
                                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
                                                className="flex-1 px-4 py-4 text-base focus:outline-none text-gray-900 placeholder-gray-400"
                                            />
                                            <button
                                                onClick={() => query && onSearch(query)}
                                                className="m-1.5 px-6 py-3 bg-[#006AFF] text-white font-semibold rounded-md hover:bg-[#0051CC] transition"
                                            >
                                                Check Visibility
                                            </button>
                                        </div>
                                    </div>

                                {/* Suggestions Dropdown */}
                                {suggestions.length > 0 && (
                                    <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-lg shadow-xl border border-gray-200 overflow-hidden z-50 max-h-80 overflow-y-auto">
                                        {suggestions.map(s => (
                                            <button
                                                key={s.id}
                                                onClick={() => onSearch(s.name)}
                                                className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center gap-3 border-b border-gray-100 last:border-0 transition"
                                            >
                                                <div className="w-10 h-10 bg-[#006AFF] text-white rounded-full flex items-center justify-center font-semibold text-sm">
                                                    {s.name ? s.name.split(' ').map(n=>n[0]).join('') : '?'}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="font-medium text-gray-900">{s.name}</div>
                                                    <div className="text-sm text-gray-500 flex items-center gap-1.5">
                                                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                                                        </svg>
                                                        <span>{s.city}, {s.state}</span>
                                                        {s.brokerage && (
                                                            <>
                                                                <span className="text-gray-300">•</span>
                                                                <span className="text-[#006AFF] truncate max-w-[180px]">{s.brokerage}</span>
                                                            </>
                                                        )}
                                                    </div>
                                                </div>
                                                <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
                                                </svg>
                                            </button>
                                        ))}
                                    </div>
                                )}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* AI Platforms Section */}
                    <div className="relative z-10 bg-white border-y border-gray-200 py-12">
                        <div className="max-w-6xl mx-auto px-6">
                            <p className="text-center text-gray-500 text-sm mb-8">Optimize your visibility across leading AI platforms</p>
                            <div className="flex flex-wrap justify-center items-center gap-12">
                                <div className="flex flex-col items-center gap-2 opacity-60 hover:opacity-100 transition">
                                    <img src={AILogos.chatgpt} alt="ChatGPT" className="h-8" />
                                    <span className="text-xs font-medium text-gray-600">ChatGPT</span>
                                </div>
                                <div className="flex flex-col items-center gap-2 opacity-60 hover:opacity-100 transition">
                                    <img src={AILogos.claude} alt="Claude" className="h-6" />
                                    <span className="text-xs font-medium text-gray-600">Claude</span>
                                </div>
                                <div className="flex flex-col items-center gap-2 opacity-60 hover:opacity-100 transition">
                                    <img src={AILogos.perplexity} alt="Perplexity" className="h-8" />
                                    <span className="text-xs font-medium text-gray-600">Perplexity</span>
                                </div>
                                <div className="flex flex-col items-center gap-2 opacity-60 hover:opacity-100 transition">
                                    <img src={AILogos.gemini} alt="Gemini" className="h-7" />
                                    <span className="text-xs font-medium text-gray-600">Gemini</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Features Section */}
                    <div className="max-w-6xl mx-auto px-6 py-16">
                        <div className="text-center mb-12">
                            <h2 className="text-3xl font-bold text-gray-900 mb-3">How It Works</h2>
                            <p className="text-gray-600">Get actionable insights to improve your AI visibility</p>
                        </div>
                        <div className="grid md:grid-cols-3 gap-8">
                            {[
                                { 
                                    icon: <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>,
                                    title: 'SALT Score Analysis', 
                                    desc: 'Semantic, Authority, Location & Trust metrics show exactly how AI platforms see you' 
                                },
                                { 
                                    icon: <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>,
                                    title: 'Market Comparison', 
                                    desc: 'See how you rank against other agents in your city and state' 
                                },
                                { 
                                    icon: <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>,
                                    title: 'Action Plan', 
                                    desc: 'Personalized recommendations to boost your visibility on AI platforms' 
                                }
                            ].map((f, i) => (
                                <div key={i} className="bg-white rounded-xl p-6 border border-gray-200 hover-lift card-shadow animate-in" style={{animationDelay: `${i * 100}ms`}}>
                                    <div className="w-12 h-12 bg-[#006AFF]/10 text-[#006AFF] rounded-lg flex items-center justify-center mb-4">
                                        {f.icon}
                                    </div>
                                    <h3 className="text-lg font-semibold text-gray-900 mb-2">{f.title}</h3>
                                    <p className="text-gray-600 text-sm">{f.desc}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Testimonial / Social Proof */}
                    <div className="bg-[#1E3A5F] py-16">
                        <div className="max-w-4xl mx-auto px-6 text-center">
                            <p className="text-white text-xl md:text-2xl font-medium mb-6">
                                "Understanding how AI recommends agents is the new frontier of real estate marketing. 
                                Don't get left behind."
                            </p>
                            <div className="flex items-center justify-center gap-3">
                                <img src={RealEstateImages.agent} alt="Expert" className="w-12 h-12 rounded-full object-cover border-2 border-white/20"/>
                                <div className="text-left">
                                    <div className="text-white font-medium">Industry Expert</div>
                                    <div className="text-gray-400 text-sm">Real Estate Technology</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Property Showcase - Commented out
                    <div className="max-w-6xl mx-auto px-6 py-16">
                        <h2 className="text-2xl font-bold text-gray-900 mb-8 text-center">Trusted by Top Agents</h2>
                        <div className="grid md:grid-cols-3 gap-6">
                            {[RealEstateImages.luxury, RealEstateImages.suburban, RealEstateImages.modern].map((img, i) => (
                                <div key={i} className="rounded-xl overflow-hidden card-shadow hover-lift">
                                    <img src={img} alt="Property" className="w-full h-48 object-cover"/>
                                    <div className="p-4 bg-white">
                                        <div className="text-sm text-gray-500">Featured Agent Market</div>
                                        <div className="font-semibold text-gray-900">Premium Visibility</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                    */}

                    <FooterSection />
                </div>
            );
        };

        // ============== SNAPSHOT PAGE ==============
        const SnapshotPage = ({ agentName, user, onBack, onUpgrade, onLogin, onLogout, onAddAgent, onViewSALT, cachedData, onDataLoaded }) => {
            const [data, setData] = useState(cachedData || null);
            const [loading, setLoading] = useState(!cachedData);
            const [showLoginModal, setShowLoginModal] = useState(false);

            const fetchData = useCallback(() => {
                // Skip fetch if we already have cached data
                if (cachedData) {
                    setData(cachedData);
                    setLoading(false);
                    return;
                }
                
                setLoading(true);
                fetch(`/api/visibility/free?name=${encodeURIComponent(agentName)}`)
                    .then(r => r.json())
                    .then(d => {
                        setData(d);
                        // Cache the data at parent level
                        if (onDataLoaded && !d.error) {
                            onDataLoaded(d);
                        }
                        setLoading(false);
                    })
                    .catch(() => {
                        setData({error: 'Failed to load data'});
                        setLoading(false);
                    });
            }, [agentName, cachedData, onDataLoaded]);

            useEffect(() => {
                // Only refetch if user login state changes and we need fresh SALT scores
                if (cachedData && user?.logged_in !== cachedData?.user_status?.logged_in) {
                    // User logged in/out - need to refresh for SALT scores
                    setLoading(true);
                    fetch(`/api/visibility/free?name=${encodeURIComponent(agentName)}`)
                        .then(r => r.json())
                        .then(d => {
                            setData(d);
                            if (onDataLoaded && !d.error) {
                                onDataLoaded(d);
                            }
                            setLoading(false);
                        })
                        .catch(() => {
                            setLoading(false);
                        });
                } else {
                    fetchData();
                }
            }, [fetchData, user?.logged_in]);

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

            // Score color based on performance
            const getScoreColor = (score) => {
                if (score >= 80) return { bg: 'bg-[#00D395]', text: 'text-[#00D395]', light: 'bg-[#00D395]/10' };
                if (score >= 60) return { bg: 'bg-[#006AFF]', text: 'text-[#006AFF]', light: 'bg-[#006AFF]/10' };
                if (score >= 40) return { bg: 'bg-[#FF9500]', text: 'text-[#FF9500]', light: 'bg-[#FF9500]/10' };
                return { bg: 'bg-[#FF3B30]', text: 'text-[#FF3B30]', light: 'bg-[#FF3B30]/10' };
            };
            const scoreStyle = getScoreColor(data.visibility_score);

            return (
                <div className="min-h-screen bg-gray-50">
                    <Navbar user={user} onLogin={() => setShowLoginModal(true)} onLogout={onLogout} onAddAgent={onAddAgent} />

                    {/* Hero Header with Property Image */}
                    <div className="relative h-48 bg-[#1E3A5F]">
                        <img 
                            src={RealEstateImages.neighborhood} 
                            alt="Neighborhood" 
                            className="absolute inset-0 w-full h-full object-cover opacity-30"
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-[#1E3A5F] to-transparent"/>
                    </div>

                    <div className="max-w-6xl mx-auto px-6 -mt-24 relative z-10 pb-12">
                        {/* Back button */}
                        <button
                            onClick={onBack}
                            className="mb-4 text-white/80 hover:text-white flex items-center gap-2 transition text-sm"
                        >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
                            </svg>
                            Back to Search
                        </button>

                        {/* Agent Profile Card */}
                        <div className="bg-white rounded-xl card-shadow-lg mb-6 overflow-hidden animate-in">
                            <div className="p-6 lg:p-8">
                                <div className="flex flex-col lg:flex-row gap-6">
                                    {/* Avatar */}
                                    <div className={`w-24 h-24 lg:w-28 lg:h-28 ${scoreStyle.bg} rounded-xl flex items-center justify-center text-white text-3xl font-bold flex-shrink-0 mx-auto lg:mx-0`}>
                                        {(data.agent.name || 'NA').split(' ').map(n => n[0]).join('')}
                                    </div>

                                    {/* Info */}
                                    <div className="flex-1 text-center lg:text-left">
                                        <h1 className="text-2xl lg:text-3xl font-bold text-gray-900 mb-2">{data.agent.name}</h1>
                                        <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4 text-gray-600 mb-4">
                                            <span className="flex items-center gap-1.5 text-sm">
                                                <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/>
                                                </svg>
                                                {data.agent.brokerage || 'Independent Agent'}
                                            </span>
                                            <span className="flex items-center gap-1.5 text-sm">
                                                <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                                                </svg>
                                                {data.agent.city}, {data.agent.state}
                                            </span>
                                        </div>
                                        <div className="flex flex-wrap items-center justify-center lg:justify-start gap-2">
                                            <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-xs font-medium">
                                                {data.agent.years_experience || 0}+ Years
                                            </span>
                                            {data.basic_metrics.average_rating > 0 && (
                                                <span className="px-3 py-1 bg-amber-50 text-amber-700 rounded-full text-xs font-medium flex items-center gap-1">
                                                    <svg className="w-3 h-3 fill-amber-500" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
                                                    {data.basic_metrics.average_rating.toFixed(1)} ({data.basic_metrics.total_reviews})
                                                </span>
                                            )}
                                            <span className="px-3 py-1 bg-blue-50 text-[#006AFF] rounded-full text-xs font-medium">
                                                {data.basic_metrics.specialization || 'Residential'}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Visibility Score Circle */}
                                    <div className="flex flex-col items-center lg:items-end">
                                        <div className="relative w-32 h-32">
                                            <svg className="w-full h-full transform -rotate-90">
                                                <circle cx="64" cy="64" r="56" fill="none" stroke="#e5e7eb" strokeWidth="8"/>
                                                <circle 
                                                    cx="64" cy="64" r="56" fill="none" 
                                                    stroke={data.visibility_score >= 80 ? '#00D395' : data.visibility_score >= 60 ? '#006AFF' : data.visibility_score >= 40 ? '#FF9500' : '#FF3B30'}
                                                    strokeWidth="8" 
                                                    strokeLinecap="round"
                                                    strokeDasharray={`${data.visibility_score * 3.52} 352`}
                                                />
                                            </svg>
                                            <div className="absolute inset-0 flex flex-col items-center justify-center">
                                                <span className="text-3xl font-bold text-gray-900">{data.visibility_score}</span>
                                                <span className="text-xs text-gray-500">out of 100</span>
                                            </div>
                                        </div>
                                        <div className={`mt-2 px-3 py-1 ${scoreStyle.light} ${scoreStyle.text} rounded-full text-xs font-semibold`}>
                                            {data.visibility_tier} Tier
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* SALT Scores Section */}
                        {isLoggedIn && data.salt_scores ? (
                            <div className="bg-white rounded-xl card-shadow mb-6 animate-in">
                                <div className="p-6 border-b border-gray-100">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h2 className="text-lg font-bold text-gray-900">SALT Score Breakdown</h2>
                                            <p className="text-sm text-gray-500">Semantic, Authority, Location & Trust metrics</p>
                                        </div>
                                        <button 
                                            onClick={onViewSALT}
                                            className="px-4 py-2 text-sm font-medium text-[#006AFF] bg-[#006AFF]/10 rounded-lg hover:bg-[#006AFF]/20 transition flex items-center gap-2"
                                        >
                                            View Details
                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/></svg>
                                        </button>
                                    </div>
                                </div>
                                <div className="p-6">
                                    <div className="grid md:grid-cols-2 gap-4">
                                        {[
                                            { label: 'Semantic', desc: 'Identity clarity', score: data.salt_scores.semantic, color: '#006AFF', barClass: 'score-bar-semantic' },
                                            { label: 'Authority', desc: 'Cite-worthiness', score: data.salt_scores.authority, color: '#8B5CF6', barClass: 'score-bar-authority' },
                                            { label: 'Location', desc: 'Market grounding', score: data.salt_scores.location, color: '#00D395', barClass: 'score-bar-location' },
                                            { label: 'Trust', desc: 'Safety to recommend', score: data.salt_scores.trust, color: '#FF9500', barClass: 'score-bar-trust' }
                                        ].map((metric, i) => (
                                            <div key={i} className="bg-gray-50 rounded-lg p-4">
                                                <div className="flex items-center justify-between mb-2">
                                                    <div>
                                                        <span className="font-semibold text-gray-900">{metric.label}</span>
                                                        <span className="text-xs text-gray-500 ml-2">{metric.desc}</span>
                                                    </div>
                                                    <span className="text-xl font-bold" style={{color: metric.color}}>{metric.score || 0}</span>
                                                </div>
                                                <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                                                    <div
                                                        className={`h-full ${metric.barClass} rounded-full transition-all duration-1000`}
                                                        style={{width: `${metric.score || 0}%`}}
                                                    />
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    {data.ranking_preview && (
                                        <div className="mt-4 p-4 bg-[#006AFF]/5 rounded-lg border border-[#006AFF]/20">
                                            <div className="flex items-center justify-center gap-2">
                                                <svg className="w-5 h-5 text-[#006AFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"/>
                                                </svg>
                                                <span className="text-sm font-medium text-gray-700">
                                                    Ranked <span className="text-[#006AFF] font-bold">#{data.ranking_preview.state_rank}</span> of {data.ranking_preview.state_total} agents in {data.ranking_preview.state}
                                                </span>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* LLM Visibility Scores with Real Logos */}
                                {data.llm_visibility_scores && (
                                    <div className="border-t border-gray-100">
                                        <div className="p-6">
                                            <h3 className="text-sm font-semibold text-gray-900 mb-4">AI Platform Visibility Scores</h3>
                                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                                {[
                                                    { name: 'ChatGPT', key: 'chatgpt', logo: AILogos.chatgpt, bgColor: 'bg-[#10A37F]/10' },
                                                    { name: 'Claude', key: 'claude', logo: AILogos.claude, bgColor: 'bg-[#D97706]/10' },
                                                    { name: 'Perplexity', key: 'perplexity', logo: AILogos.perplexity, bgColor: 'bg-[#1E3A5F]/10' },
                                                    { name: 'Gemini', key: 'gemini', logo: AILogos.gemini, bgColor: 'bg-[#4285F4]/10' }
                                                ].map((platform, i) => {
                                                    const score = data.llm_visibility_scores[platform.key] || 0;
                                                    const statusColor = score >= 80 ? 'text-[#00D395]' : score >= 60 ? 'text-[#006AFF]' : score >= 40 ? 'text-[#FF9500]' : 'text-[#FF3B30]';
                                                    return (
                                                        <div key={i} className={`${platform.bgColor} rounded-lg p-4 text-center hover-lift`}>
                                                            <img src={platform.logo} alt={platform.name} className="h-6 mx-auto mb-3 object-contain" onError={(e) => e.target.style.display='none'}/>
                                                            <div className={`text-2xl font-bold ${statusColor}`}>{score}</div>
                                                            <div className="text-xs text-gray-500 mt-1">{platform.name}</div>
                                                            <div className="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                                                                <div 
                                                                    className="h-full rounded-full transition-all duration-1000"
                                                                    style={{
                                                                        width: `${score}%`,
                                                                        backgroundColor: score >= 80 ? '#00D395' : score >= 60 ? '#006AFF' : score >= 40 ? '#FF9500' : '#FF3B30'
                                                                    }}
                                                                />
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="bg-[#1E3A5F] rounded-xl p-8 lg:p-12 text-center text-white mb-6 relative overflow-hidden animate-in">
                                <img src={RealEstateImages.office} alt="" className="absolute inset-0 w-full h-full object-cover opacity-20"/>
                                <div className="relative z-10">
                                    <div className="w-16 h-16 bg-white/10 rounded-xl flex items-center justify-center mx-auto mb-6">
                                        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                                        </svg>
                                    </div>
                                    <h2 className="text-2xl font-bold mb-3">Unlock Your SALT Score</h2>
                                    <p className="text-gray-300 mb-6 max-w-lg mx-auto text-sm">
                                        Sign in to view your detailed SALT metrics and see how you rank against competitors in your market.
                                    </p>
                                    <button
                                        onClick={() => setShowLoginModal(true)}
                                        className="px-6 py-3 bg-[#006AFF] text-white font-semibold rounded-lg hover:bg-[#0051CC] transition"
                                    >
                                        Sign In to Unlock
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Full Report CTA - Professional Style */}
                        <div className="bg-white rounded-xl card-shadow overflow-hidden mb-6 animate-in">
                            <div className="grid lg:grid-cols-2">
                                <div className="p-8 lg:p-10">
                                    <span className="inline-block px-3 py-1 bg-[#00D395]/10 text-[#00D395] text-xs font-semibold rounded-full mb-4">
                                        PREMIUM REPORT
                                    </span>
                                    <h2 className="text-2xl font-bold text-gray-900 mb-3">Get Your Full AI Visibility Report</h2>
                                    <p className="text-gray-600 mb-6">
                                        Comprehensive analysis with actionable recommendations to improve your visibility across all AI platforms.
                                    </p>
                                    <div className="space-y-3 mb-6">
                                        {[
                                            'Complete SALT score breakdown with improvement tips',
                                            'Competitor comparison in your market',
                                            'Personalized 30-day action plan',
                                            'AI platform-specific optimization guide'
                                        ].map((item, i) => (
                                            <div key={i} className="flex items-center gap-2 text-sm text-gray-700">
                                                <svg className="w-5 h-5 text-[#00D395]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/>
                                                </svg>
                                                {item}
                                            </div>
                                        ))}
                                    </div>
                                    <button
                                        onClick={onUpgrade}
                                        className="px-8 py-3 bg-[#006AFF] text-white font-semibold rounded-lg hover:bg-[#0051CC] transition"
                                    >
                                        {isPaid ? 'View Full Report' : 'Get Full Report — $49'}
                                    </button>
                                    {!isPaid && <p className="text-xs text-gray-500 mt-3">One-time payment • Instant access</p>}
                                </div>
                                <div className="hidden lg:block relative">
                                    <img src={RealEstateImages.sold} alt="Success" className="absolute inset-0 w-full h-full object-cover"/>
                                    <div className="absolute inset-0 bg-gradient-to-r from-white via-white/50 to-transparent"/>
                                </div>
                            </div>
                        </div>
                    </div>

                    <LoginModal
                        show={showLoginModal}
                        onClose={() => setShowLoginModal(false)}
                        onSuccess={(userData) => {
                            setShowLoginModal(false);
                            // Also update the parent's user state
                            if (onLogin) onLogin(userData);
                            // Refresh data without page reload - refetch with new auth
                            fetchData();
                        }}
                    />

                    <FooterSection />
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
        const FullReportPage = ({ agentName, user, onBack, onLogout, onAddAgent, onViewSALT, cachedData, onDataLoaded }) => {
            const [data, setData] = useState(cachedData || null);
            const [loading, setLoading] = useState(!cachedData);
            const [error, setError] = useState(null);

            useEffect(() => {
                // Use cached data if available
                if (cachedData) {
                    setData(cachedData);
                    setLoading(false);
                    return;
                }
                
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
                            // Cache at parent level
                            if (onDataLoaded) {
                                onDataLoaded(d);
                            }
                        }
                        setLoading(false);
                    })
                    .catch(e => {
                        setError(e.message);
                        setLoading(false);
                    });
            }, [agentName, cachedData, onDataLoaded]);

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
                            <button onClick={onBack} className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition">Go Back</button>
                        </div>
                    </div>
                );
            }

            const agent = data.agent || {};
            const analysis = data.analysis || {};
            const scores = analysis.scores || {};
            const roadmap = analysis.geo_improvement_roadmap || {};
            const gaps = analysis.competitor_gaps || {};
            const insights = analysis.actionable_insights || {};
            const recommendations = analysis.recommendations || {};
            const profileAnalysis = analysis.profile_analysis || {};
            const llmScores = analysis.llm_visibility_scores || {};

            const overallScore = scores.overall?.score || 0;
            const getScoreStyle = (score) => ({
                color: score >= 80 ? '#00D395' : score >= 60 ? '#006AFF' : score >= 40 ? '#FF9500' : '#FF3B30',
                bg: score >= 80 ? 'bg-[#00D395]' : score >= 60 ? 'bg-[#006AFF]' : score >= 40 ? 'bg-[#FF9500]' : 'bg-[#FF3B30]'
            });

            // Chart component for SALT radar
            const SALTChart = () => {
                const saltData = [
                    { label: 'S', name: 'Semantic', score: scores.semantic?.score || 0 },
                    { label: 'A', name: 'Authority', score: scores.authority?.score || 0 },
                    { label: 'L', name: 'Location', score: scores.location?.score || 0 },
                    { label: 'T', name: 'Trust', score: scores.trust?.score || 0 }
                ];
                return (
                    <div className="grid grid-cols-4 gap-4">
                        {saltData.map((item, i) => (
                            <div key={i} className="text-center">
                                <div className="relative w-20 h-20 mx-auto mb-2">
                                    <svg className="w-full h-full transform -rotate-90">
                                        <circle cx="40" cy="40" r="36" fill="none" stroke="#e5e7eb" strokeWidth="6"/>
                                        <circle 
                                            cx="40" cy="40" r="36" fill="none" 
                                            stroke={getScoreStyle(item.score).color}
                                            strokeWidth="6" 
                                            strokeLinecap="round"
                                            strokeDasharray={`${item.score * 2.26} 226`}
                                        />
                                    </svg>
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <span className="text-xl font-bold text-gray-900">{item.score}</span>
                                    </div>
                                </div>
                                <div className="text-sm font-semibold text-gray-900">{item.name}</div>
                            </div>
                        ))}
                    </div>
                );
            };

            return (
                <div className="min-h-screen bg-gray-50">
                    <Navbar user={user} onLogin={() => {}} onLogout={onLogout} onAddAgent={onAddAgent} />

                    {/* Report Header */}
                    <div className="bg-[#1E3A5F] text-white">
                        <div className="max-w-6xl mx-auto px-6 py-8">
                            <button onClick={onBack} className="mb-4 text-white/70 hover:text-white flex items-center gap-2 transition text-sm">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/></svg>
                                Back to Search
                            </button>
                            <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
                                <div className="flex items-center gap-4">
                                    <div className={`w-16 h-16 ${getScoreStyle(overallScore).bg} rounded-xl flex items-center justify-center text-white text-2xl font-bold`}>
                                        {(agent.name || 'NA').split(' ').map(n => n[0]).join('')}
                                    </div>
                                    <div>
                                        <p className="text-white/60 text-xs uppercase tracking-wide mb-1">AI Visibility Report</p>
                                        <h1 className="text-2xl font-bold">{agent.name || 'Unknown Agent'}</h1>
                                        <p className="text-white/80 text-sm">{agent.brokerage || 'Independent'} • {agent.location?.city}, {agent.location?.state}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-6">
                                    <div className="text-center">
                                        <div className="text-4xl font-bold">{overallScore}</div>
                                        <div className="text-xs text-white/60">Overall Score</div>
                                    </div>
                                    <div className="h-12 w-px bg-white/20"/>
                                    <div className="text-center">
                                        <div className="text-2xl font-bold">#{data.leaderboard_context?.state_rank || '?'}</div>
                                        <div className="text-xs text-white/60">State Rank</div>
                                    </div>
                                    <div className="h-12 w-px bg-white/20"/>
                                    <div className="text-center">
                                        <div className="text-2xl font-bold">{scores.overall?.tier || 'N/A'}</div>
                                        <div className="text-xs text-white/60">Tier</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="max-w-6xl mx-auto px-6 py-8">
                        {/* Score Overview Cards */}
                        <div className="grid lg:grid-cols-3 gap-6 mb-8">
                            {/* SALT Scores Card */}
                            <div className="lg:col-span-2 bg-white rounded-xl card-shadow p-6">
                                <div className="flex items-center justify-between mb-6">
                                    <h2 className="text-lg font-bold text-gray-900">SALT Score Breakdown</h2>
                                    <button onClick={onViewSALT} className="text-sm text-[#006AFF] hover:underline">View Details →</button>
                                </div>
                                <SALTChart />
                            </div>

                            {/* AI Platform Scores */}
                            <div className="bg-white rounded-xl card-shadow p-6">
                                <h2 className="text-lg font-bold text-gray-900 mb-4">AI Platform Visibility</h2>
                                <div className="space-y-4">
                                    {[
                                        { name: 'ChatGPT', key: 'chatgpt', logo: AILogos.chatgpt },
                                        { name: 'Claude', key: 'claude', logo: AILogos.claude },
                                        { name: 'Perplexity', key: 'perplexity', logo: AILogos.perplexity },
                                        { name: 'Gemini', key: 'gemini', logo: AILogos.gemini }
                                    ].map((p, i) => {
                                        const score = llmScores[p.key] || 0;
                                        return (
                                            <div key={i} className="flex items-center gap-3">
                                                <img src={p.logo} alt={p.name} className="w-6 h-6 object-contain" onError={(e) => e.target.style.display='none'}/>
                                                <div className="flex-1">
                                                    <div className="flex items-center justify-between mb-1">
                                                        <span className="text-sm text-gray-700">{p.name}</span>
                                                        <span className="text-sm font-bold" style={{color: getScoreStyle(score).color}}>{score}</span>
                                                    </div>
                                                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                                        <div className="h-full rounded-full" style={{width: `${score}%`, backgroundColor: getScoreStyle(score).color}}/>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>

                        {/* Executive Summary */}
                        <div className="bg-white rounded-xl card-shadow p-6 mb-8">
                            <h2 className="text-lg font-bold text-gray-900 mb-4">Executive Summary</h2>
                            <p className="text-gray-700 leading-relaxed">
                                {analysis.executive_summary || 'No summary available.'}
                            </p>
                        </div>

                        {/* Strengths & Gaps Table */}
                        <div className="grid lg:grid-cols-2 gap-6 mb-8">
                            {/* Strengths */}
                            <div className="bg-white rounded-xl card-shadow overflow-hidden">
                                <div className="px-6 py-4 bg-[#00D395]/10 border-b border-[#00D395]/20">
                                    <h2 className="font-bold text-gray-900 flex items-center gap-2">
                                        <svg className="w-5 h-5 text-[#00D395]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                        </svg>
                                        Strengths
                                    </h2>
                                </div>
                                <div className="p-6">
                                    <table className="w-full">
                                        <tbody>
                                            {(profileAnalysis.strengths || []).map((s, i) => (
                                                <tr key={i} className="border-b border-gray-100 last:border-0">
                                                    <td className="py-3 text-sm text-gray-700">{s}</td>
                                                </tr>
                                            ))}
                                            {(profileAnalysis.unique_selling_points || []).map((usp, i) => (
                                                <tr key={`usp-${i}`} className="border-b border-gray-100 last:border-0">
                                                    <td className="py-3 text-sm text-gray-700 flex items-center gap-2">
                                                        <span className="text-[#006AFF]">★</span> {usp}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            {/* Gaps */}
                            <div className="bg-white rounded-xl card-shadow overflow-hidden">
                                <div className="px-6 py-4 bg-[#FF9500]/10 border-b border-[#FF9500]/20">
                                    <h2 className="font-bold text-gray-900 flex items-center gap-2">
                                        <svg className="w-5 h-5 text-[#FF9500]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                                        </svg>
                                        Areas for Improvement
                                    </h2>
                                </div>
                                <div className="p-6">
                                    <table className="w-full">
                                        <tbody>
                                            {(gaps.missing_signals || []).map((g, i) => (
                                                <tr key={i} className="border-b border-gray-100 last:border-0">
                                                    <td className="py-3 text-sm text-gray-700">{g}</td>
                                                </tr>
                                            ))}
                                            {(gaps.visibility_blockers || []).map((b, i) => (
                                                <tr key={`block-${i}`} className="border-b border-gray-100 last:border-0">
                                                    <td className="py-3 text-sm text-gray-700">{b}</td>
                                                </tr>
                                            ))}
                                            {(gaps.content_gaps || []).map((c, i) => (
                                                <tr key={`content-${i}`} className="border-b border-gray-100 last:border-0">
                                                    <td className="py-3 text-sm text-gray-700">{c}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>

                        {/* Action Plan */}
                        <div className="bg-white rounded-xl card-shadow overflow-hidden mb-8">
                            <div className="px-6 py-4 bg-[#006AFF]/10 border-b border-[#006AFF]/20">
                                <h2 className="font-bold text-gray-900 flex items-center gap-2">
                                    <svg className="w-5 h-5 text-[#006AFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
                                    </svg>
                                    30-Day Improvement Roadmap
                                </h2>
                            </div>
                            <div className="p-6">
                                <div className="grid md:grid-cols-3 gap-6">
                                    {/* Critical */}
                                    <div>
                                        <div className="flex items-center gap-2 mb-3">
                                            <span className="w-6 h-6 bg-[#FF3B30] text-white rounded text-xs flex items-center justify-center font-bold">!</span>
                                            <span className="text-sm font-semibold text-gray-900">Critical (Week 1)</span>
                                        </div>
                                        <div className="space-y-2">
                                            {(roadmap.critical_issues || []).map((item, i) => (
                                                <div key={i} className="p-3 bg-red-50 rounded-lg text-sm text-gray-700 border-l-2 border-[#FF3B30]">{item}</div>
                                            ))}
                                        </div>
                                    </div>
                                    {/* High Priority */}
                                    <div>
                                        <div className="flex items-center gap-2 mb-3">
                                            <span className="w-6 h-6 bg-[#FF9500] text-white rounded text-xs flex items-center justify-center font-bold">2</span>
                                            <span className="text-sm font-semibold text-gray-900">High Priority (Week 2)</span>
                                        </div>
                                        <div className="space-y-2">
                                            {(roadmap.high_priority || []).map((item, i) => (
                                                <div key={i} className="p-3 bg-orange-50 rounded-lg text-sm text-gray-700 border-l-2 border-[#FF9500]">{item}</div>
                                            ))}
                                            {(roadmap.quick_wins || []).slice(0, 2).map((item, i) => (
                                                <div key={`qw-${i}`} className="p-3 bg-green-50 rounded-lg text-sm text-gray-700 border-l-2 border-[#00D395]">{item}</div>
                                            ))}
                                        </div>
                                    </div>
                                    {/* Medium */}
                                    <div>
                                        <div className="flex items-center gap-2 mb-3">
                                            <span className="w-6 h-6 bg-[#006AFF] text-white rounded text-xs flex items-center justify-center font-bold">3</span>
                                            <span className="text-sm font-semibold text-gray-900">Ongoing (Week 3-4)</span>
                                        </div>
                                        <div className="space-y-2">
                                            {(roadmap.medium_priority || []).map((item, i) => (
                                                <div key={i} className="p-3 bg-blue-50 rounded-lg text-sm text-gray-700 border-l-2 border-[#006AFF]">{item}</div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Personalized Recommendations */}
                        {(recommendations.for_agent || []).length > 0 && (
                            <div className="bg-[#1E3A5F] rounded-xl p-6 text-white mb-8">
                                <h2 className="font-bold mb-4 flex items-center gap-2">
                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z"/>
                                    </svg>
                                    Top Recommendations for You
                                </h2>
                                <div className="grid md:grid-cols-2 gap-4">
                                    {recommendations.for_agent.slice(0, 4).map((rec, i) => (
                                        <div key={i} className="bg-white/10 rounded-lg p-4 backdrop-blur">
                                            <div className="flex items-start gap-3">
                                                <span className="w-6 h-6 bg-[#006AFF] rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">{i + 1}</span>
                                                <p className="text-sm text-white/90">{rec}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* For Buyers/Sellers */}
                        <div className="grid lg:grid-cols-2 gap-6 mb-8">
                            <div className="bg-white rounded-xl card-shadow p-6">
                                <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                                    <svg className="w-5 h-5 text-[#006AFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
                                    </svg>
                                    For Home Buyers
                                </h3>
                                <ul className="space-y-2">
                                    {(insights.for_buyers || []).map((insight, i) => (
                                        <li key={i} className="text-sm text-gray-600 flex items-start gap-2">
                                            <span className="text-[#006AFF] mt-1">•</span>{insight}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            <div className="bg-white rounded-xl card-shadow p-6">
                                <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                                    <svg className="w-5 h-5 text-[#00D395]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                    </svg>
                                    For Home Sellers
                                </h3>
                                <ul className="space-y-2">
                                    {(insights.for_sellers || []).map((insight, i) => (
                                        <li key={i} className="text-sm text-gray-600 flex items-start gap-2">
                                            <span className="text-[#00D395] mt-1">•</span>{insight}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    </div>

                    <FooterSection />
                </div>
            );
        };

        // ============== SALT DETAILS PAGE ==============
        const SALTDetailsPage = ({ agentName, user, onBack, onLogout, onAddAgent, cachedData, onDataLoaded }) => {
            const [data, setData] = useState(cachedData || null);
            const [loading, setLoading] = useState(!cachedData);

            useEffect(() => {
                // Use cached data if available
                if (cachedData) {
                    setData(cachedData);
                    setLoading(false);
                    return;
                }
                
                setLoading(true);
                fetch(`/api/visibility/full?name=${encodeURIComponent(agentName)}`)
                    .then(r => r.json())
                    .then(d => {
                        setData(d);
                        // Cache at parent level
                        if (onDataLoaded && !d.error) {
                            onDataLoaded(d);
                        }
                        setLoading(false);
                    })
                    .catch(() => {
                        setData({error: 'Failed to load data'});
                        setLoading(false);
                    });
            }, [agentName, cachedData, onDataLoaded]);

            if (loading) return <LoadingScreen title="Loading SALT Analysis" subtitle="Computing visibility metrics"/>;

            if (!data || data.error) {
                return (
                    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 p-6">
                        <div className="max-w-md w-full bg-white rounded-3xl shadow-xl p-8 text-center">
                            <h2 className="text-2xl font-bold text-gray-900 mb-3">Error Loading SALT Data</h2>
                            <button onClick={onBack} className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-xl">Go Back</button>
                        </div>
                    </div>
                );
            }

            const agent = data.agent || {};
            const analysis = data.analysis || {};
            const scores = analysis.scores || {};

            const saltMetrics = [
                {
                    key: 'semantic',
                    label: 'Semantic',
                    icon: '🔍',
                    color: 'blue',
                    fullName: 'Semantic Identity',
                    question: 'Can AI identify who you are?',
                    description: 'Measures how clearly and consistently your identity appears across the web. AI systems need unambiguous signals to confidently recommend you.',
                    score: scores.semantic?.score || 0,
                    grade: scores.semantic?.grade || 'N/A',
                    factors: scores.semantic?.factors || [],
                    summary: scores.semantic?.summary || 'Identity clarity assessment based on name consistency, role positioning, and cross-platform presence.',
                    breakdown: scores.semantic?.breakdown || {},
                    improvements: [
                        'Ensure your full professional name is consistent across all platforms',
                        'Add a detailed bio (100+ words) describing your expertise and market focus',
                        'Include your brokerage affiliation and license information prominently',
                        'Create profiles on all major platforms with matching information'
                    ]
                },
                {
                    key: 'authority',
                    label: 'Authority',
                    icon: '👑',
                    color: 'purple',
                    fullName: 'Content Authority',
                    question: 'Does AI have credible content to cite?',
                    description: 'Evaluates whether you have authoritative content that AI can reference. This includes your website, reviews, social media presence, and media mentions.',
                    score: scores.authority?.score || 0,
                    grade: scores.authority?.grade || 'N/A',
                    factors: scores.authority?.factors || [],
                    summary: scores.authority?.summary || 'Authority assessment based on owned content, review volume, and cite-worthiness.',
                    breakdown: scores.authority?.breakdown || {},
                    improvements: [
                        'Build and maintain a professional website with regular content updates',
                        'Actively collect reviews on Google, Zillow, and Realtor.com (target 100+)',
                        'Establish presence on LinkedIn with recommendations from clients',
                        'Create video content and market reports to demonstrate expertise'
                    ]
                },
                {
                    key: 'location',
                    label: 'Location',
                    icon: '📍',
                    color: 'green',
                    fullName: 'Location Visibility',
                    question: 'What markets can AI associate you with?',
                    description: 'Assesses how well AI can connect you to specific geographic markets. Strong location signals help AI recommend you for local searches.',
                    score: scores.location?.score || 0,
                    grade: scores.location?.grade || 'N/A',
                    factors: scores.location?.factors || [],
                    summary: scores.location?.summary || 'Location visibility based on geographic signals and neighborhood authority.',
                    breakdown: scores.location?.breakdown || {},
                    improvements: [
                        'Add city, neighborhoods, and ZIP codes to all profiles and bios',
                        'Create neighborhood-specific pages on your website',
                        'Publish local market reports and area guides regularly',
                        'Ensure your Google Business Profile has accurate location data'
                    ]
                },
                {
                    key: 'trust',
                    label: 'Trust',
                    icon: '🛡️',
                    color: 'amber',
                    fullName: 'Trust & Safety',
                    question: 'Is it safe for AI to recommend you?',
                    description: 'Measures the risk level associated with recommending you. AI systems prioritize agents with verified credentials, positive sentiment, and strong reputation signals.',
                    score: scores.trust?.score || 0,
                    grade: scores.trust?.grade || 'N/A',
                    factors: scores.trust?.factors || [],
                    summary: scores.trust?.summary || 'Trust assessment based on sentiment, licensing verification, and reputation signals.',
                    breakdown: scores.trust?.breakdown || {},
                    improvements: [
                        'Maintain 4.7+ average rating across review platforms',
                        'Ensure license status is current and verifiable online',
                        'Respond to all reviews (positive and negative) professionally',
                        'Document and showcase successful transactions and client outcomes'
                    ]
                }
            ];

            const colorClasses = {
                blue: { bg: 'bg-blue-500', bar: 'score-bar-blue', light: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700' },
                purple: { bg: 'bg-purple-500', bar: 'score-bar-purple', light: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700' },
                green: { bg: 'bg-emerald-500', bar: 'score-bar-green', light: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700' },
                amber: { bg: 'bg-amber-500', bar: 'score-bar-amber', light: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700' }
            };

            return (
                <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
                    <Navbar user={user} onLogin={() => {}} onLogout={onLogout} onAddAgent={onAddAgent} />

                    <div className="max-w-5xl mx-auto px-6 py-8">
                        <button onClick={onBack} className="mb-6 text-gray-600 hover:text-gray-900 flex items-center gap-2 transition">
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/></svg>
                            Back to Dashboard
                        </button>

                        {/* Header */}
                        <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-8 text-white mb-8 shadow-2xl">
                            <div className="flex flex-col md:flex-row items-center gap-6">
                                <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center text-3xl font-bold">
                                    {(agent.name || 'NA').split(' ').map(n => n[0]).join('')}
                                </div>
                                <div className="flex-1 text-center md:text-left">
                                    <h1 className="text-3xl font-extrabold mb-1">{agent.name || 'Unknown Agent'}</h1>
                                    <p className="text-blue-200">SALT Score Detailed Analysis</p>
                                </div>
                                <div className="text-center">
                                    <div className="text-5xl font-extrabold">{scores.overall?.score || 0}</div>
                                    <div className="text-blue-200 text-sm">Overall Score</div>
                                </div>
                            </div>
                        </div>

                        {/* What is SALT? */}
                        <div className="bg-white rounded-3xl p-8 shadow-xl border border-gray-200 mb-8">
                            <h2 className="text-2xl font-bold text-gray-900 mb-4">What is the SALT Framework?</h2>
                            <p className="text-gray-700 leading-relaxed mb-6">
                                SALT is a comprehensive framework for measuring how visible and recommendable you are to AI systems like ChatGPT, Claude, Perplexity, and Google's AI. 
                                Each component represents a critical layer that AI uses to evaluate whether to recommend an agent.
                            </p>
                            <div className="grid md:grid-cols-4 gap-4">
                                {saltMetrics.map((metric, i) => (
                                    <div key={i} className={`${colorClasses[metric.color].light} ${colorClasses[metric.color].border} border rounded-xl p-4 text-center`}>
                                        <div className="text-3xl mb-2">{metric.icon}</div>
                                        <div className={`font-bold ${colorClasses[metric.color].text}`}>{metric.label}</div>
                                        <div className="text-xs text-gray-600">{metric.question}</div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Individual SALT Scores */}
                        <div className="space-y-6">
                            {saltMetrics.map((metric, i) => (
                                <div key={i} className="bg-white rounded-3xl shadow-xl border border-gray-200 overflow-hidden animate-in" style={{animationDelay: `${i * 100}ms`}}>
                                    <div className={`${colorClasses[metric.color].light} ${colorClasses[metric.color].border} border-b p-6`}>
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-4">
                                                <span className="text-5xl">{metric.icon}</span>
                                                <div>
                                                    <h3 className="text-2xl font-bold text-gray-900">{metric.fullName}</h3>
                                                    <p className={`${colorClasses[metric.color].text} font-medium`}>{metric.question}</p>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <div className="text-4xl font-extrabold text-gray-900">{metric.score}<span className="text-lg text-gray-500">/100</span></div>
                                                <div className={`inline-block px-3 py-1 ${colorClasses[metric.color].light} ${colorClasses[metric.color].text} rounded-full text-sm font-semibold`}>
                                                    Grade: {metric.grade}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="mt-4 h-4 bg-gray-200 rounded-full overflow-hidden">
                                            <div className={`h-full ${colorClasses[metric.color].bar} rounded-full transition-all duration-1000`} style={{width: `${metric.score}%`}}/>
                                        </div>
                                    </div>
                                    <div className="p-6">
                                        <p className="text-gray-700 mb-6">{metric.description}</p>
                                        
                                        {metric.factors.length > 0 && (
                                            <div className="mb-6">
                                                <h4 className="font-semibold text-gray-900 mb-3">Contributing Factors</h4>
                                                <div className="flex flex-wrap gap-2">
                                                    {metric.factors.map((factor, j) => (
                                                        <span key={j} className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm">
                                                            ✓ {factor}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        <div className={`${colorClasses[metric.color].light} rounded-xl p-4`}>
                                            <h4 className="font-semibold text-gray-900 mb-3">How to Improve This Score</h4>
                                            <ul className="space-y-2">
                                                {metric.improvements.map((imp, j) => (
                                                    <li key={j} className="flex items-start gap-2 text-gray-700">
                                                        <span className={`${colorClasses[metric.color].text} font-bold`}>→</span>
                                                        {imp}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Why SALT Matters */}
                        <div className="mt-8 bg-gradient-to-br from-blue-600 to-purple-600 rounded-3xl p-8 text-white">
                            <h2 className="text-2xl font-bold mb-4">Why SALT Matters for Your Business</h2>
                            <div className="grid md:grid-cols-2 gap-6">
                                <div className="bg-white/10 rounded-xl p-5">
                                    <div className="text-3xl mb-2">🤖</div>
                                    <h3 className="font-bold mb-2">AI is the New Search</h3>
                                    <p className="text-blue-100 text-sm">More consumers are asking AI assistants for agent recommendations instead of traditional search engines.</p>
                                </div>
                                <div className="bg-white/10 rounded-xl p-5">
                                    <div className="text-3xl mb-2">📈</div>
                                    <h3 className="font-bold mb-2">First-Mover Advantage</h3>
                                    <p className="text-blue-100 text-sm">Agents who optimize for AI visibility now will dominate their markets as AI adoption grows.</p>
                                </div>
                                <div className="bg-white/10 rounded-xl p-5">
                                    <div className="text-3xl mb-2">🎯</div>
                                    <h3 className="font-bold mb-2">Higher Quality Leads</h3>
                                    <p className="text-blue-100 text-sm">AI recommendations carry more weight, leading to more qualified and motivated clients.</p>
                                </div>
                                <div className="bg-white/10 rounded-xl p-5">
                                    <div className="text-3xl mb-2">💰</div>
                                    <h3 className="font-bold mb-2">Competitive Edge</h3>
                                    <p className="text-blue-100 text-sm">Most agents don't understand AI visibility yet. Optimize now to stay ahead of the competition.</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <FooterSection />
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
            
            // Centralized cache for agent data - prevents repeated loading
            const [agentDataCache, setAgentDataCache] = useState({});
            const [fullReportCache, setFullReportCache] = useState({});

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

            const handleLogin = useCallback((userData) => {
                setUser(userData);
                setShowLoginModal(false);
                // Clear cache on login to refresh with new permissions
                setAgentDataCache({});
                setFullReportCache({});
            }, []);

            const handleLogout = useCallback(async () => {
                await fetch('/api/auth/logout', { method: 'POST' });
                setUser(null);
                setPage('search');
                // Clear cache on logout
                setAgentDataCache({});
                setFullReportCache({});
            }, []);

            const handleSearch = useCallback((name) => {
                setAgentName(name);
                setPage('snapshot');
            }, []);

            const handleUpgrade = useCallback(() => {
                if (user?.paid) {
                    setPage('report');
                } else {
                    setPage('paywall');
                }
            }, [user?.paid]);

            const handlePaymentSuccess = useCallback((userData) => {
                setUser(userData);
                // Clear full report cache to refetch with paid status
                setFullReportCache({});
                setPage('report');
            }, []);

            const handleAddAgent = useCallback(() => {
                setShowAddAgentModal(true);
            }, []);

            const handleAddAgentSuccess = useCallback((result) => {
                alert(result.message);
                setShowAddAgentModal(false);
                // Clear cache for new agent
                setAgentDataCache({});
                setFullReportCache({});
                handleSearch(result.agent_name);
            }, [handleSearch]);

            const handleViewSALT = useCallback(() => {
                setPage('salt');
            }, []);

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
                            onLogin={handleLogin}
                            onLogout={handleLogout}
                            onAddAgent={handleAddAgent}
                            onViewSALT={handleViewSALT}
                            cachedData={agentDataCache[agentName?.toLowerCase()]}
                            onDataLoaded={(data) => setAgentDataCache(prev => ({...prev, [agentName?.toLowerCase()]: data}))}
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
                            onViewSALT={handleViewSALT}
                            cachedData={fullReportCache[agentName?.toLowerCase()]}
                            onDataLoaded={(data) => setFullReportCache(prev => ({...prev, [agentName?.toLowerCase()]: data}))}
                        />
                    )}
                    {page === 'salt' && (
                        <SALTDetailsPage
                            agentName={agentName}
                            user={user}
                            onBack={() => setPage(user?.paid ? 'report' : 'snapshot')}
                            onLogout={handleLogout}
                            onAddAgent={handleAddAgent}
                            cachedData={fullReportCache[agentName?.toLowerCase()]}
                            onDataLoaded={(data) => setFullReportCache(prev => ({...prev, [agentName?.toLowerCase()]: data}))}
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

def create_app():
    """Application factory for production deployments (gunicorn, etc.)"""
    # Pre-load system on app startup
    try:
        get_system()
    except Exception as e:
        print(f"⚠️ Warning: Could not pre-load system: {e}")
    return app

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Vieweo - AI Visibility Platform')
    parser.add_argument('--port', '-p', type=int, default=int(os.environ.get('PORT', 8080)), help='Port to run on')
    parser.add_argument('--host', '-H', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"🌐 Starting Vieweo on http://{args.host}:{args.port}")
    print(f"📊 Environment: {'DEBUG' if args.debug else 'PRODUCTION'}")
    print(f"{'='*60}\n")
    
    # Pre-load system
    try:
        get_system()
    except Exception as e:
        print(f"⚠️ Warning: System will load on first request: {e}")
    
    app.run(
        host=args.host, 
        port=args.port, 
        debug=args.debug, 
        use_reloader=args.debug,
        threaded=True
    )
