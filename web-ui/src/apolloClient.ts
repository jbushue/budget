import { ApolloClient, InMemoryCache, HttpLink, gql } from '@apollo/client';

// Configuration
const GRAPHQL_URL = process.env.REACT_APP_GRAPHQL_URL || 'http://localhost:4000/graphql';

// Create Apollo Client
export const client = new ApolloClient({
  link: new HttpLink({
    uri: GRAPHQL_URL,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
  }),
  cache: new InMemoryCache({
    typePolicies: {
      Query: {
        fields: {
          snapshot: {
            merge(existing, incoming) {
              return incoming;
            },
          },
          projection: {
            merge(existing, incoming) {
              return incoming;
            },
          },
        },
      },
    },
  }),
  connectToDevTools: true,
});

export default client;

