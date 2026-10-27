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


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)  # Enable CORS

    # Initialize the finance manager. One manager is shared by all requests,
    # so GraphQL operations are serialized with a lock.
    manager = FinanceManager([], [], [])
    lock = threading.Lock()
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
                    context_value={'manager': manager}
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
        return jsonify({
            'status': 'healthy',
            'banks': len(manager.banks),
            'bills': len(manager.bills),
            'income_sources': len(manager.income_sources)
        })

    # Root endpoint with API info
    @app.route('/', methods=['GET'])
    def index():
        """Root endpoint with API information."""
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

    return app


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
    app.run(debug=debug, host=host, port=4000)

