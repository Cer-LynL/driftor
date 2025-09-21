# Deployment Guide

This guide will help you deploy the Founder Matchmaker app to Vercel with Supabase.

## Prerequisites

- Vercel account
- Supabase account
- GitHub repository

## Step 1: Supabase Setup

1. **Create a new Supabase project**
   - Go to [supabase.com](https://supabase.com)
   - Click "New Project"
   - Choose your organization and enter project details
   - Wait for the project to be created

2. **Get your Supabase credentials**
   - Go to Settings > API
   - Copy your Project URL and anon/public key
   - Go to Settings > API > Service Role
   - Copy your service role key (keep this secret!)

3. **Set up the database**
   - Go to the SQL Editor in your Supabase dashboard
   - Run the migration SQL from `prisma/migrations/001_init/migration.sql`
   - Run the RLS policies from `prisma/rls-policies.sql`

4. **Enable Google OAuth (optional)**
   - Go to Authentication > Providers
   - Enable Google provider
   - Add your Google OAuth credentials

5. **Set up Realtime**
   - Go to Database > Replication
   - Enable realtime for the `messages` and `matches` tables

## Step 2: Vercel Setup

1. **Connect your repository**
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your GitHub repository
   - Choose the root directory

2. **Configure build settings**
   - Framework Preset: Next.js
   - Build Command: `npm run build`
   - Output Directory: `.next`
   - Install Command: `npm install`

3. **Add environment variables**
   - Go to Settings > Environment Variables
   - Add the following variables:

   ```
   NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
   DATABASE_URL=your_supabase_database_url
   NEXT_PUBLIC_SITE_URL=https://your-app.vercel.app
   ```

4. **Deploy**
   - Click "Deploy"
   - Wait for the deployment to complete

## Step 3: Post-Deployment Setup

1. **Update Supabase settings**
   - Go to Authentication > URL Configuration
   - Add your Vercel URL to "Site URL"
   - Add `https://your-app.vercel.app/auth/callback` to "Redirect URLs"

2. **Seed the database**
   - Run the seed script locally or use Supabase's SQL editor
   - This will populate your database with demo data

3. **Test the application**
   - Visit your Vercel URL
   - Test sign up, sign in, and core functionality
   - Verify that realtime features work

## Step 4: Custom Domain (Optional)

1. **Add custom domain in Vercel**
   - Go to Settings > Domains
   - Add your custom domain
   - Follow the DNS configuration instructions

2. **Update Supabase settings**
   - Update "Site URL" and "Redirect URLs" with your custom domain

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL | Yes |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Your Supabase anon key | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | Your Supabase service role key | Yes |
| `DATABASE_URL` | Your Supabase database URL | Yes |
| `NEXT_PUBLIC_SITE_URL` | Your app's URL (for redirects) | Yes |
| `RESEND_API_KEY` | For email notifications (optional) | No |
| `UPSTASH_REDIS_REST_URL` | For rate limiting (optional) | No |
| `UPSTASH_REDIS_REST_TOKEN` | For rate limiting (optional) | No |

## Troubleshooting

### Common Issues

1. **Database connection errors**
   - Verify your `DATABASE_URL` is correct
   - Check that RLS policies are properly set up
   - Ensure your Supabase project is active

2. **Authentication not working**
   - Verify your Supabase URL and keys
   - Check that redirect URLs are configured correctly
   - Ensure Google OAuth is set up if using it

3. **Realtime not working**
   - Check that realtime is enabled for the correct tables
   - Verify your service role key has the correct permissions

4. **Build failures**
   - Check that all environment variables are set
   - Verify your Node.js version (should be 18+)
   - Check the build logs for specific errors

### Getting Help

- Check the [Supabase documentation](https://supabase.com/docs)
- Check the [Vercel documentation](https://vercel.com/docs)
- Check the [Next.js documentation](https://nextjs.org/docs)

## Monitoring

1. **Vercel Analytics**
   - Enable Vercel Analytics in your dashboard
   - Monitor performance and usage

2. **Supabase Monitoring**
   - Use Supabase's built-in monitoring
   - Set up alerts for database issues

3. **Error Tracking**
   - Consider adding Sentry or similar for error tracking
   - Monitor application errors and performance

## Security Checklist

- [ ] RLS policies are properly configured
- [ ] Service role key is kept secret
- [ ] Environment variables are properly set
- [ ] HTTPS is enabled (automatic with Vercel)
- [ ] CORS is properly configured
- [ ] Rate limiting is implemented (if using Upstash)

## Performance Optimization

1. **Database**
   - Add appropriate indexes
   - Use connection pooling
   - Monitor query performance

2. **Frontend**
   - Enable Vercel's edge caching
   - Optimize images
   - Use Next.js Image component

3. **API**
   - Implement proper caching
   - Use database indexes
   - Monitor API response times
