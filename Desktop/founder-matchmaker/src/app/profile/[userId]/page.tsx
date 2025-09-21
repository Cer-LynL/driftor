'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { ArrowLeft, Heart, MessageCircle, User as UserIcon, MapPin, Building, Calendar, ExternalLink } from 'lucide-react'
import { FaWhatsapp, FaLinkedin, FaGithub } from 'react-icons/fa'
import Link from 'next/link'
import { toast } from 'sonner'

interface UserProfile {
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
  languages?: string[]
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
    problem?: string
    solution?: string
    websiteUrl?: string
    imageUrls?: string[]
    logoUrl?: string
    hiringNeeds?: string[]
  }>
}

export default function UserProfilePage() {
  const params = useParams()
  const router = useRouter()
  const userId = params.userId as string
  
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isLiking, setIsLiking] = useState(false)
  const [hasLiked, setHasLiked] = useState(false)

  useEffect(() => {
    if (userId) {
      loadUserProfile()
    }
  }, [userId])

  const loadUserProfile = async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/profile/${userId}`)
      if (response.ok) {
        const data = await response.json()
        setProfile(data)
      } else {
        toast.error('Failed to load user profile')
        router.push('/dashboard')
      }
    } catch (error) {
      console.error('Error loading user profile:', error)
      toast.error('Failed to load user profile')
      router.push('/dashboard')
    } finally {
      setIsLoading(false)
    }
  }

  const handleLike = async () => {
    if (isLiking || hasLiked) return

    setIsLiking(true)
    try {
      const response = await fetch('/api/like', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ toUserId: userId })
      })

      if (response.ok) {
        const result = await response.json()
        setHasLiked(true)
        
        if (result.isMatch) {
          toast.success("🎉 It&apos;s a match! You can now chat with this person.")
        } else {
          toast.success("Like sent! You&apos;ll be notified if they like you back.")
        }
      } else {
        const error = await response.json()
        toast.error(error.error || 'Failed to send like')
      }
    } catch (error) {
      console.error('Error sending like:', error)
      toast.error('Failed to send like')
    } finally {
      setIsLiking(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500">Loading profile...</div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-500 mb-4">Profile not found</p>
          <Button onClick={() => router.push('/dashboard')}>
            Back to Dashboard
          </Button>
        </div>
      </div>
    )
  }

  const skills = profile.skills.map(s => s.skill.name)
  const offers = profile.offers.map(o => o.tag)
  const lookingFor = profile.lookingFor.map(l => l.tag)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <Button variant="ghost" size="sm" onClick={() => router.back()}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <h1 className="text-xl font-semibold text-gray-900 ml-4">
              {profile.name || 'User Profile'}
            </h1>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-6">
          {/* Profile Header */}
          <Card>
            <CardContent className="p-6">
              <div className="flex items-start space-x-6">
                <Avatar className="h-24 w-24">
                  <AvatarImage src={profile.imageUrl} />
                  <AvatarFallback className="text-xl">
                    {(profile.name || 'U').charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <h1 className="text-2xl font-bold text-gray-900">
                    {profile.name || 'Anonymous User'}
                  </h1>
                  {profile.headline && (
                    <p className="text-lg text-gray-600 mt-1">{profile.headline}</p>
                  )}
                  <div className="flex items-center mt-2 text-gray-500">
                    {profile.location && (
                      <div className="flex items-center mr-4">
                        <MapPin className="w-4 h-4 mr-1" />
                        {profile.location}
                      </div>
                    )}
                    {profile.availability !== undefined && (
                      <div className="flex items-center">
                        <UserIcon className="w-4 h-4 mr-1" />
                        {profile.availability}% available
                      </div>
                    )}
                  </div>
                  <div className="flex items-center space-x-3 mt-4">
                    <Button 
                      onClick={handleLike}
                      disabled={isLiking || hasLiked}
                      className={hasLiked ? 'bg-red-500 hover:bg-red-600' : ''}
                    >
                      <Heart className={`h-4 w-4 mr-2 ${hasLiked ? 'fill-white' : ''}`} />
                      {isLiking ? 'Sending...' : hasLiked ? 'Liked' : 'Like'}
                    </Button>
                    {profile.whatsapp && (
                      <Link 
                        href={`https://wa.me/${profile.whatsapp.replace(/[^0-9]/g, '')}`} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="hover:scale-110 transition-transform"
                      >
                        <FaWhatsapp className="w-8 h-8 text-green-500 hover:text-green-600" />
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Bio */}
          {profile.bio && (
            <Card>
              <CardHeader>
                <CardTitle>About</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-600 leading-relaxed">{profile.bio}</p>
              </CardContent>
            </Card>
          )}

          {/* Skills & Expertise */}
          <div className="grid gap-6 md:grid-cols-2">
            {/* Skills */}
            {skills.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Skills</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {skills.map((skill, index) => (
                      <Badge key={index} variant="secondary">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* What they offer */}
            {offers.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>What I Offer</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {offers.map((offer, index) => (
                      <Badge key={index} variant="outline">
                        {offer}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* What they're looking for */}
            {lookingFor.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>What I&apos;m Looking For</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {lookingFor.map((item, index) => (
                      <Badge key={index} variant="default">
                        {item}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Work Preferences */}
            <Card>
              <CardHeader>
                <CardTitle>Work Preferences</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {profile.remotePref && (
                  <div>
                    <span className="font-medium text-gray-900">Work Style:</span>
                    <span className="ml-2 text-gray-600 capitalize">{profile.remotePref}</span>
                  </div>
                )}
                {profile.equityPref && (
                  <div>
                    <span className="font-medium text-gray-900">Equity Preference:</span>
                    <span className="ml-2 text-gray-600 capitalize">{profile.equityPref}</span>
                  </div>
                )}
                {profile.languages && profile.languages.length > 0 && (
                  <div>
                    <span className="font-medium text-gray-900">Languages:</span>
                    <span className="ml-2 text-gray-600">{profile.languages.join(', ')}</span>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Social Links */}
          {(profile.linkedin || profile.github) && (
            <Card>
              <CardHeader>
                <CardTitle>Links</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex gap-3 flex-wrap">
                  {profile.linkedin && (
                    <Link 
                      href={profile.linkedin} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="hover:scale-110 transition-transform"
                    >
                      <FaLinkedin className="w-8 h-8 text-blue-600 hover:text-blue-700" />
                    </Link>
                  )}
                  {profile.github && (
                    <Link 
                      href={profile.github} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="hover:scale-110 transition-transform"
                    >
                      <FaGithub className="w-8 h-8 text-gray-800 hover:text-gray-900" />
                    </Link>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Startups */}
          {profile.startups && profile.startups.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Startups</CardTitle>
                <CardDescription>
                  Companies and projects they're working on
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2">
                  {profile.startups.map((startup) => (
                    <Card key={startup.id} className="border-l-4 border-l-blue-500">
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
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
                          <Badge variant="outline" className="capitalize">
                            {startup.stage}
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="pt-0">
                        <div className="space-y-3">
                          {startup.problem && (
                            <div>
                              <h5 className="font-medium text-gray-900 text-sm">Problem</h5>
                              <p className="text-sm text-gray-600">{startup.problem}</p>
                            </div>
                          )}
                          {startup.solution && (
                            <div>
                              <h5 className="font-medium text-gray-900 text-sm">Solution</h5>
                              <p className="text-sm text-gray-600">{startup.solution}</p>
                            </div>
                          )}
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
                          {startup.hiringNeeds && startup.hiringNeeds.length > 0 && (
                            <div>
                              <h5 className="font-medium text-gray-900 text-sm mb-1">Hiring</h5>
                              <div className="flex flex-wrap gap-1">
                                {startup.hiringNeeds.map((role, index) => (
                                  <Badge key={index} variant="destructive" className="text-xs">
                                    {role}
                                  </Badge>
                                ))}
                              </div>
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
                          {startup.websiteUrl && (
                            <Button variant="outline" size="sm" asChild>
                              <Link href={startup.websiteUrl} target="_blank" rel="noopener noreferrer">
                                <ExternalLink className="w-4 h-4 mr-2" />
                                Visit Website
                              </Link>
                            </Button>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
