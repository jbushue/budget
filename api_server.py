#!/usr/bin/env python3
"""
GraphQL Server for Personal Finance Management System
Provides a GraphQL API endpoint for React Native and web clients.

Run with: python api_server.py
Then access GraphQL playground at: http://localhost:4000/graphql

Environment:
  BUDGET_HOST             address to listen on (default 127.0.0.1; 0.0.0.0 for other devices)
  BUDGET_PORT             port (default 4000)
  BUDGET_DATA_DIR         where the database and backups live (default ~/.budget_app)
  BUDGET_TRUSTED_PROXIES  number of reverse proxies in front (e.g. 1 behind Caddy/nginx), so
                          client addresses and HTTPS are read from their X-Forwarded-* headers
  BUDGET_THREADS          worker threads (default 8)
  BUDGET_DEBUG            1 = Flask's development server with auto-reload (never on a network)
"""

import os
import threading

from flask import Flask, jsonify, request
from flask_cors import CORS
from models.graphql_schema import schema
from models.finance_manager import FinanceManager
from models import activity, auth, jobs, web_routes


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    # The web app (and the Vite dev server, through its proxy) is same-origin,
    # so cross-origin requests are off unless origins are listed: an open CORS
    # policy would let any website in your browser read this API before the
    # first account is set up.
    origins = [o.strip() for o in os.environ.get('BUDGET_CORS_ORIGINS', '').split(',') if o.strip()]
    if origins:
        CORS(app, origins=origins)

    # Behind a reverse proxy: believe its X-Forwarded-For / -Proto / -Host (only that many hops)
    proxies = int(os.environ.get('BUDGET_TRUSTED_PROXIES') or 0)
    if proxies > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies)

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
        operation_name = data.get('operationName')

        if not query:
            return jsonify({'errors': [{'message': 'No query provided'}]}), 400

        try:
            # Execute the query
            with lock:
                result = schema.execute(
                    query,
                    variable_values=variables,
                    operation_name=operation_name,
                    context_value={'manager': state['manager']}
                )
            if result.data and not result.errors and 'mutation' in query:
                try:
                    activity.record_mutations(query, variables, operation_name, result.data,
                                              web_routes.current_user())
                except Exception as e:  # history must never break a change that succeeded
                    print(f"⚠️  Couldn't record activity: {e}")

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


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("🏦 PERSONAL FINANCE GRAPHQL API SERVER")
    print("=" * 80)
    port = int(os.environ.get('BUDGET_PORT') or 4000)
    print("\n📍 Starting GraphQL server...")
    print(f"\n✓ GraphQL Playground: http://localhost:{port}/graphql")
    print(f"✓ Health Check: http://localhost:{port}/health")
    print(f"✓ API Info: http://localhost:{port}/")
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
        print(f"   curl -X POST http://localhost:{port}/auth/password -H 'Content-Type: application/json' \\")
        print(f"        -d '{{\"username\": \"admin\", \"current_password\": \"{initial_password}\", "
              "\"new_password\": \"<your password>\"}'")
        print("=" * 80 + "\n")

    if not debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        jobs.start(app)  # backups, SimpleFIN sync, digest, push, daily maintenance
    if debug:
        app.run(debug=True, host=host, port=port)
    else:
        try:
            from waitress import serve
        except ImportError:
            print("⚠️  waitress isn't installed (pip install waitress) — using Flask's development server")
            app.run(host=host, port=port)
        else:
            threads = int(os.environ.get('BUDGET_THREADS') or 8)
            print(f"✓ Serving on http://{host}:{port} with waitress ({threads} threads)")
            serve(app, host=host, port=port, threads=threads, ident='budget')

