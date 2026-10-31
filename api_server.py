#!/usr/bin/env python3
"""
GraphQL Server for Personal Finance Management System
Provides a GraphQL API endpoint for React Native and web clients.

Run with: python api_server.py
Then access GraphQL playground at: http://localhost:4000/graphql
"""

import os
import threading

from flask import Flask, jsonify, request
from flask_cors import CORS
from models.graphql_schema import schema
from models.finance_manager import FinanceManager
from models import auth, web_routes


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)  # Enable CORS

    # Initialize the finance manager. One manager is shared by all requests,
    # so GraphQL operations are serialized with a lock. It lives in `state` so
    # a backup restore can swap in a freshly loaded one.
    manager = FinanceManager([], [], [])
    lock = threading.Lock()
    state = {'manager': manager}
    app.config['BUDGET_STATE'] = state
    app.config['BUDGET_LOCK'] = lock
    manager.initialize_database()

    # Try to load from database
    try:
        if manager.load_from_database():
            print("✓ Loaded data from database")
            # Auto-reset bill periods that have rolled over
            reset_count = manager.auto_reset_periods()
            if reset_count > 0:
                print(f"✓ Auto-reset {reset_count} bill period(s)")
            # Record daily net worth snapshot
            snap = manager.record_net_worth_snapshot()
            if snap:
                print(f"✓ Net worth snapshot: ${snap['net_worth']:,.2f}")
        else:
            print("ℹ️  No data in database. Use GraphQL mutations to create data.")
    except Exception as e:
        print(f"⚠️  Could not load database: {e}")

    # GraphQL endpoint
    @app.route('/graphql', methods=['GET', 'POST', 'OPTIONS'])
    def graphql_endpoint():
        """GraphQL endpoint for queries and mutations."""
        if request.method == 'OPTIONS':
            return '', 204

        if request.method == 'GET':
            # Serve GraphiQL playground
            return '''
            <!DOCTYPE html>
            <html>
              <head>
                <title>GraphQL Playground</title>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/graphiql@3/graphiql.min.css" />
                <style>
                  body { margin: 0; height: 100vh; }
                  #root { height: 100%; }
                </style>
              </head>
              <body>
                <div id="root"></div>
                <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
                <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
                <script src="https://cdn.jsdelivr.net/npm/graphiql@3/graphiql.min.js"></script>
                <script>
                  const fetcher = GraphiQL.createFetcher({
                    url: '/graphql',
                  });
                  ReactDOM.createRoot(document.getElementById('root')).render(
                    React.createElement(GraphiQL, { fetcher }),
                  );
                </script>
              </body>
            </html>
            '''

        # Handle POST requests
        data = request.get_json(silent=True) or {}
        query = data.get('query')
        variables = data.get('variables')

        if not query:
            return jsonify({'errors': [{'message': 'No query provided'}]}), 400

        try:
            # Execute the query
            with lock:
                result = schema.execute(
                    query,
                    variable_values=variables,
                    context_value={'manager': state['manager']}
                )

            response = {}
            if result.data:
                response['data'] = result.data
            if result.errors:
                response['errors'] = [{'message': str(e)} for e in result.errors]

            # Always return 200 for GraphQL responses per the GraphQL-over-HTTP spec.
            # Errors are communicated in the response body, not via HTTP status codes.
            # Returning 400 causes Apollo client to throw network errors.
            return jsonify(response), 200
        except Exception as e:
            return jsonify({'errors': [{'message': str(e)}]}), 500

    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint."""
        m = state['manager']
        return jsonify({
            'status': 'healthy',
            'banks': len(m.banks),
            'bills': len(m.bills),
            'income_sources': len(m.income_sources)
        })

    # Login, file downloads/uploads, and the built web UI (if present)
    web_routes.register(app, state, lock)

    # API info (at / unless the built web UI is being served there)
    @app.route('/api', methods=['GET'])
    def index():
        """API information."""
        manager = state['manager']
        return jsonify({
            'name': 'Personal Finance Management System GraphQL API',
            'version': '1.0.0',
            'endpoints': {
                'graphql': '/graphql',
                'health': '/health'
            },
            'data': {
                'banks': len(manager.banks),
                'bills': len(manager.bills),
                'income_sources': len(manager.income_sources)
            }
        })

    if not os.path.isdir(web_routes.DIST_DIR):
        app.add_url_rule('/', 'api_root', index, methods=['GET'])

    return app


def start_digest_thread(app):
    """Send the optional daily email digest (checks every 30 minutes)."""
    from models import alerts

    def loop():
        while True:
            try:
                if alerts.digest_due():
                    with app.config['BUDGET_LOCK']:
                        print('✉️ ', alerts.send_digest(app.config['BUDGET_STATE']['manager']))
            except Exception as e:  # keep the server running whatever happens
                print(f'⚠️  Digest email failed: {e}')
            threading.Event().wait(1800)

    threading.Thread(target=loop, daemon=True, name='digest').start()


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("🏦 PERSONAL FINANCE GRAPHQL API SERVER")
    print("=" * 80)
    print("\n📍 Starting GraphQL server...")
    print("\n✓ GraphQL Playground: http://localhost:4000/graphql")
    print("✓ Health Check: http://localhost:4000/health")
    print("✓ API Info: http://localhost:4000/")
    print("\n" + "=" * 80 + "\n")

    # Debug mode (auto-reload + interactive debugger) is opt-in: the Werkzeug
    # debugger allows arbitrary code execution, so never expose it on the network.
    debug = os.environ.get('BUDGET_DEBUG') == '1'
    host = os.environ.get('BUDGET_HOST', '127.0.0.1')
    app = create_app()

    # First start: an admin account with a random password, so a headless server can be set up from a shell
    initial_password = auth.ensure_default_admin()
    if initial_password:
        print("=" * 80)
        print("🔑 Created the admin account. Its password is shown here and saved in")
        print(f"   {auth.initial_password_file()} until you change it.")
        print(f"\n   username: {auth.DEFAULT_ADMIN}\n   password: {initial_password}\n")
        print("   Change it in the web UI (Settings → Your account), or from a shell:")
        print("   curl -X POST http://localhost:4000/auth/password -H 'Content-Type: application/json' \\")
        print(f"        -d '{{\"username\": \"admin\", \"current_password\": \"{initial_password}\", "
              "\"new_password\": \"<your password>\"}'")
        print("=" * 80 + "\n")

    if not debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        start_digest_thread(app)
    app.run(debug=debug, host=host, port=4000)

