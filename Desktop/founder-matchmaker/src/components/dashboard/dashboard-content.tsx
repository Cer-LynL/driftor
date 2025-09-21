'use client'

import { useState, useEffect } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { User } from '@supabase/supabase-js'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Heart, MessageCircle, User as UserIcon, MapPin, Building, Calendar, ExternalLink, Trash2, LogOut, Filter, Settings, Check, X } from 'lucide-react'
import { FaWhatsapp, FaLinkedin, FaGithub } from 'react-icons/fa'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import Link from 'next/link'
import { toast } from 'sonner'
import { createClient } from '@/lib/supabase/client'

interface ProfileData {
  id: string
  email: string
  name?: string
  headline?: string
  bio?: string
  location?: string
  timezone?: string
  availability?: number
  equityPref?: string
  remotePref?: string
  languages?: string
  imageUrl?: string
  whatsapp?: string
  linkedin?: string
  github?: string
  skills: Array<{
    skill: {
      name: string
    }
  }>
  offers: Array<{
    tag: string
  }>
  lookingFor: Array<{
    tag: string
  }>
  startups?: Array<{
    id: string
    name: string
    oneLiner: string
    stage: string
    markets: string[]
    teamSize?: number
    createdAt: string
  }>
}

interface Startup {
  id: string
  name: string
  oneLiner: string
  stage: string
  markets: string[]
  teamSize?: number
  createdAt: string
  logoUrl?: string
  hiringNeeds?: string[]
}

interface Match {
  id: string
  user: {
    id: string
    name: string
    imageUrl?: string
    headline: string
  }
  lastMessage?: string
  timestamp?: string
  unread?: boolean
}

interface RecommendedUser {
  id: string
  name?: string
  headline?: string
  bio?: string
  location?: string
  imageUrl?: string
  skills: Array<{
    skill: {
      name: string
    }
  }>
  offers: Array<{
    tag: string
  }>
  lookingFor: Array<{
    tag: string
  }>
  availability?: number
  matchScore?: number
  matchReasons?: string[]
  startups?: Array<{
    id: string
    name: string
    oneLiner: string
    stage: string
  }>
}

interface Invitation {
  id: string
  fromId: string
  toId: string
  message?: string
  createdAt: string
}

interface DashboardContentProps {
  user: User
}

export function DashboardContent({ user }: DashboardContentProps) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const supabase = createClient()
  const [activeTab, setActiveTab] = useState('discover')
  const [profileData, setProfileData] = useState<ProfileData | null>(null)
  const [startups, setStartups] = useState<Startup[]>([])
  const [matches, setMatches] = useState<Match[]>([])
  const [recommendations, setRecommendations] = useState<RecommendedUser[]>([])
  const [filteredRecommendations, setFilteredRecommendations] = useState<RecommendedUser[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMatches, setIsLoadingMatches] = useState(false)
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false)
  const [likedUsers, setLikedUsers] = useState<Set<string>>(new Set())
  const [likingUser, setLikingUser] = useState<string | null>(null)
  const [deletingStartup, setDeletingStartup] = useState<string | null>(null)
  
  // Invitation popup states
  const [showInvitationDialog, setShowInvitationDialog] = useState(false)
  const [selectedUser, setSelectedUser] = useState<RecommendedUser | null>(null)
  const [invitationMessage, setInvitationMessage] = useState('Hey! I saw your profile and I think we could build something amazing together.')
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [isLoadingInvitations, setIsLoadingInvitations] = useState(false)
  
  // Filter states
  const [searchKeyword, setSearchKeyword] = useState('')
  const [filterByStartups, setFilterByStartups] = useState<'all' | 'with' | 'without'>('all')
  const [filterByLocation, setFilterByLocation] = useState('')
  const [activeSkillFilter, setActiveSkillFilter] = useState<'all' | 'technical' | 'business' | 'design'>('all')

  useEffect(() => {
    // Check for tab parameter in URL
    const tabParam = searchParams.get('tab')
    if (tabParam && ['discover', 'matches', 'profile'].includes(tabParam)) {
      setActiveTab(tabParam)
    }
  }, [searchParams])

  useEffect(() => {
    if (activeTab === 'discover') {
      loadRecommendations()
    } else if (activeTab === 'profile') {
      loadProfileData()
      loadStartups()
    } else if (activeTab === 'matches') {
      loadMatches()
    }
  }, [activeTab])

  // Filter recommendations whenever filters change
  useEffect(() => {
    applyFilters()
  }, [recommendations, searchKeyword, filterByStartups, filterByLocation, activeSkillFilter])

  const applyFilters = () => {
    let filtered = [...recommendations]

    // Keyword search (skills, offers, looking for, name, headline, bio)
    if (searchKeyword.trim()) {
      const keyword = searchKeyword.toLowerCase()
      filtered = filtered.filter(user => {
        const skills = user.skills.map(s => s.skill.name.toLowerCase()).join(' ')
        const offers = user.offers.map(o => o.tag.toLowerCase()).join(' ')
        const lookingFor = user.lookingFor.map(l => l.tag.toLowerCase()).join(' ')
        const name = (user.name || '').toLowerCase()
        const headline = (user.headline || '').toLowerCase()
        const bio = (user.bio || '').toLowerCase()
        
        return skills.includes(keyword) || 
               offers.includes(keyword) || 
               lookingFor.includes(keyword) ||
               name.includes(keyword) ||
               headline.includes(keyword) ||
               bio.includes(keyword)
      })
    }

    // Filter by startup presence
    if (filterByStartups === 'with') {
      filtered = filtered.filter(user => 
        user.startups && user.startups.length > 0
      )
    } else if (filterByStartups === 'without') {
      filtered = filtered.filter(user => 
        !user.startups || user.startups.length === 0
      )
    }

    // Filter by location
    if (filterByLocation.trim()) {
      const location = filterByLocation.toLowerCase()
      filtered = filtered.filter(user => 
        (user.location || '').toLowerCase().includes(location)
      )
    }

    // Filter by skill category
    if (activeSkillFilter !== 'all') {
      const technicalSkills = ['React', 'Vue.js', 'Angular', 'Node.js', 'Python', 'Java', 'Go', 'Rust', 'TypeScript', 'JavaScript', 'PostgreSQL', 'MongoDB', 'Redis', 'AWS', 'Docker', 'Kubernetes', 'GraphQL', 'REST API', 'Machine Learning', 'AI', 'Data Science', 'DevOps', 'Security', 'Mobile Development', 'Web3', 'Blockchain']
      const businessSkills = ['Product Management', 'Marketing', 'Sales', 'Operations', 'Finance', 'Legal', 'Business Development', 'Growth Marketing', 'Content Marketing']
      const designSkills = ['UI/UX Design', 'Product Design', 'Graphic Design', 'Brand Design']

      filtered = filtered.filter(user => {
        const userSkills = user.skills.map(s => s.skill.name)
        const userOffers = user.offers.map(o => o.tag)
        const allUserSkills = [...userSkills, ...userOffers]

        switch (activeSkillFilter) {
          case 'technical':
            return allUserSkills.some(skill => technicalSkills.includes(skill))
          case 'business':
            return allUserSkills.some(skill => businessSkills.includes(skill))
          case 'design':
            return allUserSkills.some(skill => designSkills.includes(skill))
          default:
            return true
        }
      })
    }

    setFilteredRecommendations(filtered)
  }

  const handleDeleteStartup = async (startupId: string) => {
    if (!confirm('Are you sure you want to delete this startup? This action cannot be undone.')) {
      return
    }

    setDeletingStartup(startupId)
    try {
      const response = await fetch(`/api/startups/${startupId}`, {
        method: 'DELETE'
      })

      if (response.ok) {
        toast.success('Startup deleted successfully!')
        loadStartups() // Reload startups
      } else {
        const error = await response.json()
        toast.error(error.error || 'Failed to delete startup')
      }
    } catch (error) {
      console.error('Error deleting startup:', error)
      toast.error('Failed to delete startup')
    } finally {
      setDeletingStartup(null)
    }
  }

  const loadProfileData = async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/profile')
      if (response.ok) {
        const data = await response.json()
        setProfileData(data)
      }
    } catch (error) {
      console.error('Error loading profile:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadStartups = async () => {
    try {
      const response = await fetch('/api/startups')
      if (response.ok) {
        const data = await response.json()
        setStartups(data)
      }
    } catch (error) {
      console.error('Error loading startups:', error)
    }
  }

  const loadRecommendations = async () => {
    setIsLoadingRecommendations(true)
    try {
      const response = await fetch('/api/recommendations')
      if (response.ok) {
        const data = await response.json()
        setRecommendations(data)
      } else {
        console.error('Failed to load recommendations')
        setRecommendations([])
      }
    } catch (error) {
      console.error('Error loading recommendations:', error)
      setRecommendations([])
    } finally {
      setIsLoadingRecommendations(false)
    }
  }

  const loadMatches = async () => {
    setIsLoadingMatches(true)
    try {
      const response = await fetch('/api/matches')
      if (response.ok) {
        const data = await response.json()
        setMatches(data)
      } else {
        // If no real matches, use mock data for now
        setMatches(mockMatches)
      }
    } catch (error) {
      console.error('Error loading matches:', error)
      // Fallback to mock data
      setMatches(mockMatches)
    } finally {
      setIsLoadingMatches(false)
    }
  }

  const handleLikeClick = (recommendedUser: RecommendedUser) => {
    if (likedUsers.has(recommendedUser.id) || likingUser === recommendedUser.id) return
    
    setSelectedUser(recommendedUser)
    setShowInvitationDialog(true)
  }

  const handleSendInvitation = async () => {
    if (!selectedUser) return

    setLikingUser(selectedUser.id)
    try {
      const response = await fetch('/api/like', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          toUserId: selectedUser.id,
          message: invitationMessage 
        })
      })

      if (response.ok) {
        const result = await response.json()
        setLikedUsers(prev => new Set([...prev, selectedUser.id]))
        setShowInvitationDialog(false)
        
        if (result.isMatch) {
          toast.success('🎉 It&apos;s a match! You can now connect via WhatsApp.')
          // Refresh matches if we're on the matches tab
          if (activeTab === 'matches') {
            loadMatches()
          }
        } else {
          toast.success('Invitation sent! You&apos;ll be notified if they like you back.')
        }
      } else {
        const error = await response.json()
        toast.error(error.error || 'Failed to send invitation')
      }
    } catch (error) {
      console.error('Error sending invitation:', error)
      toast.error('Failed to send invitation')
    } finally {
      setLikingUser(null)
      setSelectedUser(null)
      setInvitationMessage('Hey! I saw your profile and I think we could build something amazing together.')
    }
  }

  const handleLogout = async () => {
    try {
      await supabase.auth.signOut()
      toast.success('Logged out successfully!')
      router.push('/')
    } catch (error) {
      console.error('Error logging out:', error)
      toast.error('Failed to log out')
    }
  }


  const mockMatches = [
    {
      id: '1',
      user: {
        name: 'Alex Kim',
        imageUrl: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150&h=150&fit=crop&crop=face',
        headline: 'AI/ML Engineer with startup experience'
      },
      lastMessage: 'Hey! I saw your profile and I think we could build something amazing together.',
      timestamp: '2 hours ago',
      unread: true
    },
    {
      id: '2',
      user: {
        name: 'Jessica Wang',
        imageUrl: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&h=150&fit=crop&crop=face',
        headline: 'Marketing expert and growth hacker'
      },
      lastMessage: 'Thanks for the connection! Let&apos;s schedule a call this week.',
      timestamp: '1 day ago',
      unread: false
    }
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">Founder Matchmaker</h1>
            </div>
            <div className="flex items-center space-x-4">
              <Avatar>
                <AvatarImage src={profileData?.imageUrl || user.user_metadata?.avatar_url} />
                <AvatarFallback>
                  {(profileData?.name || user.user_metadata?.name || user.email)?.charAt(0)?.toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="discover">Discover</TabsTrigger>
            <TabsTrigger value="matches">Matches</TabsTrigger>
            <TabsTrigger value="profile">Profile</TabsTrigger>
          </TabsList>

          <TabsContent value="discover" className="space-y-6">
            {/* Filter Controls */}
            <Card>
              <CardContent className="p-4 space-y-4">
                {/* Search and Location */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Search Keywords</label>
                    <Input
                      placeholder="Search skills, offers, names..."
                      value={searchKeyword}
                      onChange={(e) => setSearchKeyword(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Location</label>
                    <Input
                      placeholder="Filter by location..."
                      value={filterByLocation}
                      onChange={(e) => setFilterByLocation(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Startup Status</label>
                    <Select value={filterByStartups} onValueChange={(value: 'all' | 'with' | 'without') => setFilterByStartups(value)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Users</SelectItem>
                        <SelectItem value="with">With Startups</SelectItem>
                        <SelectItem value="without">Without Startups</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Skill Category Filters */}
                <div className="flex flex-wrap gap-4 items-center">
                  <div className="flex items-center space-x-2">
                    <Filter className="h-4 w-4 text-gray-500" />
                    <span className="text-sm font-medium">Skill Categories:</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge 
                      variant={activeSkillFilter === 'all' ? 'default' : 'outline'} 
                      className="cursor-pointer hover:bg-gray-100"
                      onClick={() => setActiveSkillFilter('all')}
                    >
                      All Skills
                    </Badge>
                    <Badge 
                      variant={activeSkillFilter === 'technical' ? 'default' : 'outline'} 
                      className="cursor-pointer hover:bg-gray-100"
                      onClick={() => setActiveSkillFilter('technical')}
                    >
                      Technical
                    </Badge>
                    <Badge 
                      variant={activeSkillFilter === 'business' ? 'default' : 'outline'} 
                      className="cursor-pointer hover:bg-gray-100"
                      onClick={() => setActiveSkillFilter('business')}
                    >
                      Business
                    </Badge>
                    <Badge 
                      variant={activeSkillFilter === 'design' ? 'default' : 'outline'} 
                      className="cursor-pointer hover:bg-gray-100"
                      onClick={() => setActiveSkillFilter('design')}
                    >
                      Design
                    </Badge>
                  </div>
                  <div className="flex items-center space-x-2 ml-auto">
                    <span className="text-sm text-gray-500">
                      {filteredRecommendations.length} {filteredRecommendations.length === 1 ? 'match' : 'matches'}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {isLoadingRecommendations ? (
              <div className="flex items-center justify-center py-8">
                <div className="text-gray-500">Loading recommendations...</div>
              </div>
            ) : filteredRecommendations.length > 0 ? (
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {filteredRecommendations.map((recommendedUser) => {
                  const skills = recommendedUser.skills.map(s => s.skill.name)
                  const offers = recommendedUser.offers.map(o => o.tag)
                  const lookingFor = recommendedUser.lookingFor.map(l => l.tag)
                  
                  return (
                    <Card key={recommendedUser.id} className="hover:shadow-lg transition-shadow">
                      <CardHeader>
                        <div className="flex items-center space-x-4">
                          <Avatar>
                            <AvatarImage src={recommendedUser.imageUrl} />
                            <AvatarFallback>
                              {(recommendedUser.name || 'U').charAt(0).toUpperCase()}
                            </AvatarFallback>
                          </Avatar>
                          <div className="flex-1">
                            <CardTitle className="text-lg">
                              {recommendedUser.name || 'Anonymous User'}
                            </CardTitle>
                            <CardDescription className="text-sm">
                              {recommendedUser.headline || 'No headline set'}
                            </CardDescription>
                          </div>
                          {recommendedUser.matchScore && (
                            <Badge variant="outline" className="text-xs">
                              {recommendedUser.matchScore}% match
                            </Badge>
                          )}
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {recommendedUser.bio && (
                          <p className="text-sm text-gray-600 line-clamp-3">
                            {recommendedUser.bio}
                          </p>
                        )}
                        
                        {skills.length > 0 && (
                          <div className="space-y-2">
                            <div className="flex flex-wrap gap-1">
                              {skills.slice(0, 3).map((skill) => (
                                <Badge key={skill} variant="secondary" className="text-xs">
                                  {skill}
                                </Badge>
                              ))}
                              {skills.length > 3 && (
                                <Badge variant="outline" className="text-xs">
                                  +{skills.length - 3} more
                                </Badge>
                              )}
                            </div>
                          </div>
                        )}

                        {(offers.length > 0 || lookingFor.length > 0) && (
                          <div className="space-y-2">
                            {offers.length > 0 && (
                              <div className="text-xs text-gray-500">
                                <strong>Offers:</strong> {offers.join(', ')}
                              </div>
                            )}
                            {lookingFor.length > 0 && (
                              <div className="text-xs text-gray-500">
                                <strong>Looking for:</strong> {lookingFor.join(', ')}
                              </div>
                            )}
                          </div>
                        )}

                        {recommendedUser.matchReasons && recommendedUser.matchReasons.length > 0 && (
                          <div className="text-xs text-blue-600">
                            <strong>Match reasons:</strong> {recommendedUser.matchReasons.join(', ')}
                          </div>
                        )}

                        {recommendedUser.startups && recommendedUser.startups.length > 0 && (
                          <div className="space-y-2">
                            <div className="text-xs text-gray-700 font-medium">
                              <Building className="w-3 h-3 inline mr-1" />
                              Startup: {recommendedUser.startups[0].name}
                            </div>
                            <div className="text-xs text-gray-500">
                              {recommendedUser.startups[0].oneLiner}
                            </div>
                            <Badge variant="outline" className="text-xs capitalize">
                              {recommendedUser.startups[0].stage}
                            </Badge>
                          </div>
                        )}

                        <div className="flex items-center justify-between">
                          <div className="text-sm text-gray-500">
                            {recommendedUser.location && `${recommendedUser.location} • `}
                            {recommendedUser.availability !== undefined && `${recommendedUser.availability}% available`}
                          </div>
                          <div className="flex space-x-2">
                            <Button size="sm" variant="outline" asChild>
                              <Link href={`/profile/${recommendedUser.id}`}>
                                <UserIcon className="h-4 w-4" />
                              </Link>
                            </Button>
                            <Button 
                              size="sm" 
                              onClick={() => handleLikeClick(recommendedUser)}
                              disabled={likedUsers.has(recommendedUser.id) || likingUser === recommendedUser.id}
                              className={likedUsers.has(recommendedUser.id) ? 'bg-red-500 hover:bg-red-600' : ''}
                            >
                              <Heart className={`h-4 w-4 ${likedUsers.has(recommendedUser.id) ? 'fill-white' : ''}`} />
                              {likingUser === recommendedUser.id && <span className="ml-1">...</span>}
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            ) : (
              <div className="text-center py-8">
                <Heart className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500 mb-4">No recommendations available</p>
                <p className="text-sm text-gray-400">Complete your profile to get better matches!</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="matches" className="space-y-6">
            {isLoadingMatches ? (
              <div className="flex items-center justify-center py-8">
                <div className="text-gray-500">Loading matches...</div>
              </div>
            ) : matches.length > 0 ? (
              <div className="space-y-4">
                {matches.map((match) => (
                  <Card key={match.id} className="hover:shadow-md transition-shadow">
                    <CardContent className="p-6">
                      <div className="flex items-center space-x-4">
                        <Avatar>
                          <AvatarImage src={match.user.imageUrl} />
                          <AvatarFallback>{match.user.name.charAt(0)}</AvatarFallback>
                        </Avatar>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <div>
                              <h3 className="font-semibold">{match.user.name}</h3>
                              <p className="text-sm text-gray-500">{match.user.headline}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-sm text-gray-500">{match.timestamp}</p>
                              {match.unread && (
                                <div className="w-2 h-2 bg-blue-500 rounded-full mt-1 ml-auto"></div>
                              )}
                            </div>
                          </div>
                          {match.lastMessage && (
                            <p className="text-sm text-gray-600 mt-2">{match.lastMessage}</p>
                          )}
                        </div>
                        <Button size="sm" asChild>
                          <Link href={`/chat/${match.id}`}>
                            <MessageCircle className="h-4 w-4 mr-2" />
                            Chat
                          </Link>
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <MessageCircle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500 mb-4">No matches yet</p>
                <p className="text-sm text-gray-400">Start liking profiles to find your co-founder!</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="profile" className="space-y-6">
            {/* Profile Information */}
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle>Your Profile</CardTitle>
                    <CardDescription>
                      Your profile information and settings
                    </CardDescription>
                  </div>
                  <Button asChild>
                    <Link href="/profile/edit">Edit Profile</Link>
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="text-gray-500">Loading profile...</div>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Basic Info */}
                    <div className="flex items-start space-x-4">
                      <Avatar className="h-20 w-20">
                        <AvatarImage src={profileData?.imageUrl || user.user_metadata?.avatar_url} />
                        <AvatarFallback className="text-lg">
                          {(profileData?.name || user.user_metadata?.name || user.email)?.charAt(0)?.toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1">
                        <h3 className="text-xl font-semibold">
                          {profileData?.name || user.user_metadata?.name || 'No name set'}
                        </h3>
                        <p className="text-gray-600 flex items-center mt-1">
                          <UserIcon className="w-4 h-4 mr-1" />
                          {user.email}
                        </p>
                        {profileData?.headline && (
                          <p className="text-gray-700 font-medium mt-2">{profileData.headline}</p>
                        )}
                        {profileData?.location && (
                          <p className="text-gray-600 flex items-center mt-1">
                            <MapPin className="w-4 h-4 mr-1" />
                            {profileData.location}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Bio */}
                    {profileData?.bio && (
                      <div>
                        <h4 className="font-semibold text-gray-900 mb-2">About</h4>
                        <p className="text-gray-600 leading-relaxed">{profileData.bio}</p>
                      </div>
                    )}

                    {/* Skills */}
                    {profileData?.skills && profileData.skills.length > 0 && (
                      <div>
                        <h4 className="font-semibold text-gray-900 mb-2">Skills</h4>
                        <div className="flex flex-wrap gap-2">
                          {profileData.skills.map((skillItem, index) => (
                            <Badge key={index} variant="secondary">
                              {skillItem.skill.name}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Offers */}
                    {profileData?.offers && profileData.offers.length > 0 && (
                      <div>
                        <h4 className="font-semibold text-gray-900 mb-2">What I Offer</h4>
                        <div className="flex flex-wrap gap-2">
                          {profileData.offers.map((offer, index) => (
                            <Badge key={index} variant="outline">
                              {offer.tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Looking For */}
                    {profileData?.lookingFor && profileData.lookingFor.length > 0 && (
                      <div>
                        <h4 className="font-semibold text-gray-900 mb-2">What I&apos;m Looking For</h4>
                        <div className="flex flex-wrap gap-2">
                          {profileData.lookingFor.map((lookingForItem, index) => (
                            <Badge key={index} variant="default">
                              {lookingForItem.tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Additional Info */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {profileData?.availability !== undefined && (
                        <div>
                          <h4 className="font-semibold text-gray-900 mb-1">Availability</h4>
                          <p className="text-gray-600">{profileData.availability}%</p>
                        </div>
                      )}
                      {profileData?.remotePref && (
                        <div>
                          <h4 className="font-semibold text-gray-900 mb-1">Work Preference</h4>
                          <p className="text-gray-600 capitalize">{profileData.remotePref}</p>
                        </div>
                      )}
                    </div>

                    {/* Social Links */}
                    {(profileData?.linkedin || profileData?.github || profileData?.whatsapp) && (
                      <div>
                        <h4 className="font-semibold text-gray-900 mb-2">Contact & Links</h4>
                        <div className="flex gap-3 flex-wrap">
                          {profileData.whatsapp && (
                            <Link 
                              href={`https://wa.me/${profileData.whatsapp.replace(/[^0-9]/g, '')}`} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="hover:scale-110 transition-transform"
                            >
                              <FaWhatsapp className="w-8 h-8 text-green-500 hover:text-green-600" />
                            </Link>
                          )}
                          {profileData.linkedin && (
                            <Link 
                              href={profileData.linkedin} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="hover:scale-110 transition-transform"
                            >
                              <FaLinkedin className="w-8 h-8 text-blue-600 hover:text-blue-700" />
                            </Link>
                          )}
                          {profileData.github && (
                            <Link 
                              href={profileData.github} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="hover:scale-110 transition-transform"
                            >
                              <FaGithub className="w-8 h-8 text-gray-800 hover:text-gray-900" />
                            </Link>
                          )}
                        </div>
                      </div>
                    )}

                    {!profileData && (
                      <div className="text-center py-8">
                        <p className="text-gray-500 mb-4">Complete your profile to get better matches</p>
                        <Button asChild>
                          <Link href="/profile/edit">Complete Profile</Link>
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Startups Section */}
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle>Your Startups</CardTitle>
                    <CardDescription>
                      Startups you've created or are working on
                    </CardDescription>
                  </div>
                  <Button variant="outline" asChild>
                    <Link href="/startup/new">Add Startup</Link>
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {startups.length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    {startups.map((startup) => (
                      <Card key={startup.id} className="border-l-4 border-l-blue-500">
                        <CardHeader className="pb-3">
                          <div className="flex items-start justify-between">
                            <div>
                              {startup.logoUrl && (
                                <div className="mb-3">
                                  <img 
                                    src={startup.logoUrl} 
                                    alt={`${startup.name} logo`}
                                    className="h-16 w-auto max-w-32 object-contain rounded"
                                  />
                                </div>
                              )}
                              <CardTitle className="text-lg">{startup.name}</CardTitle>
                              <CardDescription className="mt-1">
                                {startup.oneLiner}
                              </CardDescription>
                            </div>
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="capitalize">
                                {startup.stage}
                              </Badge>
                              <Button variant="ghost" size="sm" asChild>
                                <Link href={`/startup/edit/${startup.id}`}>
                                  <Settings className="h-4 w-4" />
                                </Link>
                              </Button>
                              <Button 
                                variant="ghost" 
                                size="sm"
                                onClick={() => handleDeleteStartup(startup.id)}
                                disabled={deletingStartup === startup.id}
                                className="text-red-500 hover:text-red-700 hover:bg-red-50"
                              >
                                {deletingStartup === startup.id ? (
                                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-red-500 border-t-transparent" />
                                ) : (
                                  <Trash2 className="h-4 w-4" />
                                )}
                              </Button>
                            </div>
                          </div>
                        </CardHeader>
                        <CardContent className="pt-0">
                          <div className="space-y-2">
                            {startup.markets.length > 0 && (
                              <div className="flex flex-wrap gap-1">
                                {startup.markets.slice(0, 3).map((market, index) => (
                                  <Badge key={index} variant="secondary" className="text-xs">
                                    {market}
                                  </Badge>
                                ))}
                                {startup.markets.length > 3 && (
                                  <Badge variant="outline" className="text-xs">
                                    +{startup.markets.length - 3} more
                                  </Badge>
                                )}
                              </div>
                            )}
                            <div className="flex items-center justify-between text-sm text-gray-500">
                              <div className="flex items-center">
                                <Building className="w-4 h-4 mr-1" />
                                {startup.teamSize ? `${startup.teamSize} team members` : 'Team size not set'}
                              </div>
                              <div className="flex items-center">
                                <Calendar className="w-4 h-4 mr-1" />
                                {new Date(startup.createdAt).toLocaleDateString()}
                              </div>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <Building className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-500 mb-4">No startups yet</p>
                    <Button asChild>
                      <Link href="/startup/new">Create Your First Startup</Link>
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* Invitation Dialog */}
      <Dialog open={showInvitationDialog} onOpenChange={setShowInvitationDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Send Invitation</DialogTitle>
            <DialogDescription>
              Send a personalized message to {selectedUser?.name || 'this user'} to start building something together.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {selectedUser && (
              <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                <Avatar>
                  <AvatarImage src={selectedUser.imageUrl} />
                  <AvatarFallback>
                    {(selectedUser.name || 'U').charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-medium">{selectedUser.name || 'Anonymous User'}</p>
                  <p className="text-sm text-gray-500">{selectedUser.headline || 'No headline'}</p>
                </div>
              </div>
            )}
            <div className="space-y-2">
              <label className="text-sm font-medium">Your message:</label>
              <Textarea
                value={invitationMessage}
                onChange={(e) => setInvitationMessage(e.target.value)}
                placeholder="Write a personalized message..."
                rows={4}
                className="resize-none"
              />
            </div>
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setShowInvitationDialog(false)
                setSelectedUser(null)
                setInvitationMessage('Hey! I saw your profile and I think we could build something amazing together.')
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSendInvitation}
              disabled={likingUser === selectedUser?.id || !invitationMessage.trim()}
            >
              {likingUser === selectedUser?.id ? (
                <>
                  <div className="w-4 h-4 animate-spin rounded-full border-2 border-white border-t-transparent mr-2" />
                  Sending...
                </>
              ) : (
                <>
                  <Heart className="w-4 h-4 mr-2" />
                  Send Invitation
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
