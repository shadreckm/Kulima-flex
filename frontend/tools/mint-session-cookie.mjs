/* Mint a NextAuth-format JWE session cookie for integration testing.
 * Mirrors next-auth v4 jwt.encode(): A256GCM dir, HKDF(SHA256, secret, salt="", info="NextAuth.js Generated Encryption Key").
 * Usage: node tools/mint-session-cookie.mjs <secret> [sub]
 */
import { EncryptJWT, base64url, calculateJwkThumbprint } from 'jose'

const [secret, sub = 'e2e-user-42'] = process.argv.slice(2)
if (!secret) {
  console.error('usage: node tools/mint-session-cookie.mjs <secret> [sub]')
  process.exit(1)
}

// same key derivation as next-auth/jwt getDerivedEncryptionKey
async function getDerivedEncryptionKey(keyMaterial, salt) {
  const encoder = new TextEncoder()
  const keyIdentifier = 'NextAuth.js Generated Encryption Key'
  const password = encoder.encode(keyMaterial)
  const saltBits = encoder.encode(salt)
  const info = encoder.encode(keyIdentifier + (salt ? ` (${salt})` : ''))
  const key = await crypto.subtle.importKey('raw', password, 'HKDF', false, ['deriveBits'])
  const derivedBits = await crypto.subtle.deriveBits(
    { name: 'HKDF', hash: 'SHA-256', salt: saltBits, info },
    key,
    256,
  )
  return derivedBits
}

const now = () => Math.floor(Date.now() / 1000)
const derivedBits = await getDerivedEncryptionKey(secret, '')
const encryptionSecret = new Uint8Array(derivedBits)
const jwt = await new EncryptJWT({ sub, name: 'E2E Tester', email: 'e2e@example.com' })
  .setProtectedHeader({ alg: 'dir', enc: 'A256GCM' })
  .setIssuedAt()
  .setExpirationTime(now() + 30 * 24 * 60 * 60)
  .encrypt(encryptionSecret)

console.log(jwt)
