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
  FOR UPDATE USING (auth.uid()::text = id);

-- Users can create their own profile
CREATE POLICY "Users can create own profile" ON users
  FOR INSERT WITH CHECK (auth.uid()::text = id);

-- Skills are public
CREATE POLICY "Skills are public" ON skills
  FOR SELECT USING (true);

-- Skill relationships are public
CREATE POLICY "Skill relationships are public" ON skill_on_user
  FOR SELECT USING (true);

-- Users can manage their own skill relationships
CREATE POLICY "Users can manage own skills" ON skill_on_user
  FOR ALL USING (auth.uid()::text = "userId");

-- Offers and looking for are public
CREATE POLICY "Offers are public" ON offers
  FOR SELECT USING (true);

CREATE POLICY "Looking for are public" ON looking_for
  FOR SELECT USING (true);

-- Users can manage their own offers and looking for
CREATE POLICY "Users can manage own offers" ON offers
  FOR ALL USING (auth.uid()::text = "userId");

CREATE POLICY "Users can manage own looking for" ON looking_for
  FOR ALL USING (auth.uid()::text = "userId");

-- Startups are public
CREATE POLICY "Startups are public" ON startups
  FOR SELECT USING (true);

-- Users can manage their own startups
CREATE POLICY "Users can manage own startups" ON startups
  FOR ALL USING (auth.uid()::text = "ownerId");

-- Likes are public for reading
CREATE POLICY "Likes are public" ON likes
  FOR SELECT USING (true);

-- Users can create likes
CREATE POLICY "Users can create likes" ON likes
  FOR INSERT WITH CHECK (auth.uid()::text = "fromId");

-- Matches are only visible to participants
CREATE POLICY "Matches are visible to participants" ON matches
  FOR SELECT USING (auth.uid()::text = "userAId" OR auth.uid()::text = "userBId");

-- Messages are only visible to match participants
CREATE POLICY "Messages are visible to match participants" ON messages
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM matches 
      WHERE matches.id = messages."matchId" 
      AND (matches."userAId" = auth.uid()::text OR matches."userBId" = auth.uid()::text)
    )
  );

-- Users can create messages in their matches
CREATE POLICY "Users can create messages in matches" ON messages
  FOR INSERT WITH CHECK (
    auth.uid()::text = "senderId" AND
    EXISTS (
      SELECT 1 FROM matches 
      WHERE matches.id = messages."matchId" 
      AND (matches."userAId" = auth.uid()::text OR matches."userBId" = auth.uid()::text)
    )
  );

-- Reports are only visible to the reporter
CREATE POLICY "Reports are visible to reporter" ON reports
  FOR SELECT USING (auth.uid()::text = "reporterId");

-- Users can create reports
CREATE POLICY "Users can create reports" ON reports
  FOR INSERT WITH CHECK (auth.uid()::text = "reporterId");

-- Add full-text search indexes
CREATE INDEX users_search_idx ON users USING gin(to_tsvector('english', COALESCE(headline, '') || ' ' || COALESCE(bio, '')));
CREATE INDEX startups_search_idx ON startups USING gin(to_tsvector('english', one_liner || ' ' || COALESCE(problem, '') || ' ' || COALESCE(solution, '')));
