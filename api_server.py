#!/usr/bin/env python3
"""
GraphQL Server for Personal Finance Management System
Provides a GraphQL API endpoint for React Native and web clients.

Run with: python api_server.py
Then access GraphQL playground at: http://localhost:4000/graphql
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from models.graphql_schema import schema
from models.finance_manager import FinanceManager


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)  # Enable CORS

    # Initialize the finance manager
    manager = FinanceManager([], [], [])
    manager.initialize_database()

    # Try to load from database
    try:
        if manager.load_from_database():
            print("✓ Loaded data from database")
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
                <script src="https://cdn.jsdelivr.net/npm/graphiql@3/graphiql.min.js"></script>
                <script>
                  const fetcher = GraphiQL.createFetcher({
                    url: '/graphql',
                  });
                  ReactDOM.render(
                    React.createElement(GraphiQL, { fetcher }),
                    document.getElementById('root'),
                  );
                </script>
              </body>
            </html>
            '''

        # Handle POST requests
        data = request.get_json()
        query = data.get('query')
        variables = data.get('variables')

        if not query:
            return jsonify({'errors': [{'message': 'No query provided'}]}), 400

        try:
            # Execute the query
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

            return jsonify(response), 200 if not result.errors else 400
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

    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=4000)

