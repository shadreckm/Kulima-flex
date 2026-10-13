import NextAuth, { NextAuthOptions } from "next-auth"
import AzureADProvider from "next-auth/providers/azure-ad"
import GoogleProvider from "next-auth/providers/google"

// Build provider list dynamically so unconfigured providers are never registered.
// Registering GoogleProvider with empty clientId/clientSecret causes NextAuth
// to fail the OpenID discovery fetch when the sign-in challenge is issued.
const providers: NextAuthOptions["providers"] = []

if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
  providers.push(
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    })
  )
}

// Only register Azure AD if all three required credentials are present.
if (
  process.env.AZURE_AD_CLIENT_ID &&
  process.env.AZURE_AD_CLIENT_SECRET &&
  process.env.AZURE_AD_TENANT_ID
) {
  providers.push(
    AzureADProvider({
      clientId: process.env.AZURE_AD_CLIENT_ID,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET,
      tenantId: process.env.AZURE_AD_TENANT_ID,
    })
  )
}

const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  pages: {
    signIn: '/auth/signin',
  },
  session: {
    strategy: "jwt",
  },
  providers,
  callbacks: {
    async jwt({ token }) {
      // Ensure 'sub' is always present so the backend validator can resolve
      // the user from tokens minted outside the /api/v1 proxy (direct
      // large-file uploads read this same token shape).
      if (!token.sub) {
        token.sub = token.name || token.email || crypto.randomUUID()
      }
      return token
    },
    async session({ session, token }) {
      if (token?.sub) {
        ;(session as any).userId = token.sub
      }
      return session
    },
  },
}

const handler = NextAuth(authOptions)

export { handler as GET, handler as POST }
