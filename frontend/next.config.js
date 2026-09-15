/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Increase the body size limit for the API proxy route so large PDFs (up to 25 MB)
  // can be forwarded to the FastAPI backend without a 413 error.
  // The default Next.js limit is 4 MB which caused 413 on files > ~4.5 MB.
  api: {
    bodyParser: {
      sizeLimit: '26mb',
    },
    responseLimit: false,
  },
  experimental: {
    // Required for App Router route handlers to accept large multipart uploads.
    serverActions: {
      bodySizeLimit: '26mb',
    },
  },
}
module.exports = nextConfig
