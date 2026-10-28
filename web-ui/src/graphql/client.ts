import { ApolloClient, InMemoryCache, HttpLink } from '@apollo/client/core'
import { onAuthFailure } from '../utils/auth'

const httpLink = new HttpLink({
  uri: '/graphql',
  credentials: 'same-origin',
  // Notice when the session has expired (or a password was just set elsewhere)
  fetch: async (input, init) => {
    const res = await fetch(input, init)
    if (res.status === 401 || res.status === 403) onAuthFailure()
    return res
  },
})

export const apolloClient = new ApolloClient({
  link: httpLink,
  cache: new InMemoryCache(),
  defaultOptions: {
    watchQuery: { fetchPolicy: 'network-only' },
    query: { fetchPolicy: 'network-only' },
  },
})
