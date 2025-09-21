# Founder Matchmaker

A production-ready web app for connecting founders and co-founders. Built with Next.js 14, Supabase, and Prisma.

## Features

- **Authentication**: Email/password, Google OAuth, and magic link authentication
- **Profile Management**: Complete onboarding flow with skills, offers, and preferences
- **Smart Matching**: AI-powered matching algorithm based on skills, preferences, and compatibility
- **Real-time Chat**: Instant messaging with typing indicators and read receipts
- **Discovery Feed**: Browse and filter potential co-founders
- **Startup Profiles**: Optional startup information and deck sharing
- **Admin Panel**: Moderation tools and user management

## Tech Stack

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: Supabase (Auth, Database, Realtime, Storage)
- **Database**: PostgreSQL with Prisma ORM
- **Validation**: Zod
- **Animations**: Framer Motion
- **Deployment**: Vercel-ready

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn
- Supabase account
- PostgreSQL database (or use Supabase's hosted database)

### 1. Clone and Install

```bash
git clone <repository-url>
cd founder-matchmaker
npm install
```

### 2. Environment Setup

Create a `.env.local` file in the root directory:

```env
# Supabase Configuration
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url_here
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/founder_matchmaker

# Email (Optional)
RESEND_API_KEY=your_resend_api_key_here

# Redis (Optional)
UPSTASH_REDIS_REST_URL=your_upstash_redis_url_here
UPSTASH_REDIS_REST_TOKEN=your_upstash_redis_token_here

# App Configuration
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

### 3. Database Setup

```bash
# Generate Prisma client
npm run db:generate

# Push schema to database
npm run db:push

# Seed with demo data
npm run db:seed
```

### 4. Supabase Setup

1. Create a new Supabase project
2. Go to Settings > API to get your URL and keys
3. Enable Google OAuth in Authentication > Providers
4. Set up Row Level Security (RLS) policies (see Database Setup section)

### 5. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Database Setup

### RLS Policies

Run these SQL commands in your Supabase SQL editor:

```sql
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE skill_on_user ENABLE ROW LEVEL SECURITY;
ALTER TABLE offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE looking_for ENABLE ROW LEVEL SECURITY;
ALTER TABLE startups ENABLE ROW LEVEL SECURITY;
ALTER TABLE likes ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

-- Users can read public profile fields
CREATE POLICY "Users can read public profiles" ON users
  FOR SELECT USING (true);

-- Users can only update their own profile
CREATE POLICY "Users can update own profile" ON users
  FOR UPDATE USING (auth.uid() = id);

-- Users can create their own profile
CREATE POLICY "Users can create own profile" ON users
  FOR INSERT WITH CHECK (auth.uid() = id);

-- Skills are public
CREATE POLICY "Skills are public" ON skills
  FOR SELECT USING (true);

-- Skill relationships are public
CREATE POLICY "Skill relationships are public" ON skill_on_user
  FOR SELECT USING (true);

-- Users can manage their own skill relationships
CREATE POLICY "Users can manage own skills" ON skill_on_user
  FOR ALL USING (auth.uid() = user_id);

-- Offers and looking for are public
CREATE POLICY "Offers are public" ON offers
  FOR SELECT USING (true);

CREATE POLICY "Looking for are public" ON looking_for
  FOR SELECT USING (true);

-- Users can manage their own offers and looking for
CREATE POLICY "Users can manage own offers" ON offers
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own looking for" ON looking_for
  FOR ALL USING (auth.uid() = user_id);

-- Startups are public
CREATE POLICY "Startups are public" ON startups
  FOR SELECT USING (true);

-- Users can manage their own startups
CREATE POLICY "Users can manage own startups" ON startups
  FOR ALL USING (auth.uid() = owner_id);

-- Likes are public for reading
CREATE POLICY "Likes are public" ON likes
  FOR SELECT USING (true);

-- Users can create likes
CREATE POLICY "Users can create likes" ON likes
  FOR INSERT WITH CHECK (auth.uid() = from_id);

-- Matches are only visible to participants
CREATE POLICY "Matches are visible to participants" ON matches
  FOR SELECT USING (auth.uid() = user_a_id OR auth.uid() = user_b_id);

-- Messages are only visible to match participants
CREATE POLICY "Messages are visible to match participants" ON messages
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM matches 
      WHERE matches.id = messages.match_id 
      AND (matches.user_a_id = auth.uid() OR matches.user_b_id = auth.uid())
    )
  );

-- Users can create messages in their matches
CREATE POLICY "Users can create messages in matches" ON messages
  FOR INSERT WITH CHECK (
    auth.uid() = sender_id AND
    EXISTS (
      SELECT 1 FROM matches 
      WHERE matches.id = messages.match_id 
      AND (matches.user_a_id = auth.uid() OR matches.user_b_id = auth.uid())
    )
  );

-- Reports are only visible to the reporter
CREATE POLICY "Reports are visible to reporter" ON reports
  FOR SELECT USING (auth.uid() = reporter_id);

-- Users can create reports
CREATE POLICY "Users can create reports" ON reports
  FOR INSERT WITH CHECK (auth.uid() = reporter_id);
```

### Full-Text Search

```sql
-- Add full-text search indexes
CREATE INDEX users_search_idx ON users USING gin(to_tsvector('english', headline || ' ' || bio));
CREATE INDEX startups_search_idx ON startups USING gin(to_tsvector('english', one_liner || ' ' || COALESCE(problem, '') || ' ' || COALESCE(solution, '')));
```

## API Routes

- `GET /api/profile` - Get current user's profile
- `POST /api/profile` - Create/update user profile
- `GET /api/recommendations` - Get recommended matches
- `POST /api/like` - Like a user
- `GET /api/matches` - Get user's matches
- `GET /api/matches/[id]/messages` - Get messages for a match
- `POST /api/matches/[id]/messages` - Send a message

## Project Structure

```
src/
├── app/                    # Next.js App Router
│   ├── api/               # API routes
│   ├── auth/              # Authentication pages
│   ├── chat/              # Chat pages
│   ├── dashboard/         # Dashboard
│   └── onboarding/        # Onboarding flow
├── components/            # React components
│   ├── ui/               # shadcn/ui components
│   └── dashboard/        # Dashboard components
├── lib/                  # Utilities and configurations
│   ├── supabase/         # Supabase client setup
│   ├── validations/      # Zod schemas
│   └── prisma.ts         # Prisma client
└── prisma/               # Database schema and migrations
    └── seed.ts           # Seed script
```

## Deployment

### Vercel Deployment

1. Push your code to GitHub
2. Connect your repository to Vercel
3. Add environment variables in Vercel dashboard
4. Deploy!

### Environment Variables for Production

Make sure to set these in your Vercel environment:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL`
- `NEXT_PUBLIC_SITE_URL`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For support, email support@foundermatchmaker.com or create an issue in the repository.