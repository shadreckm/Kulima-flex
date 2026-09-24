/* Decode check: use next-auth's own decode to validate the minted cookie. */
import { decode } from 'next-auth/jwt'

const [secret, cookie] = process.argv.slice(2)
const payload = await decode({ token: cookie, secret })
console.log(JSON.stringify(payload))
