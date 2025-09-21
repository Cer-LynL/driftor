'use client'

import { useState, useEffect } from 'react'
import { createClient } from '@/lib/supabase/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Check, Plus, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { ImageUpload } from '@/components/ui/image-upload'

const SKILLS_OPTIONS = [
  'React', 'Vue.js', 'Angular', 'Node.js', 'Python', 'Java', 'Go', 'Rust',
  'TypeScript', 'JavaScript', 'PostgreSQL', 'MongoDB', 'Redis', 'AWS', 'Docker',
  'Kubernetes', 'GraphQL', 'REST API', 'Machine Learning', 'AI', 'Data Science',
  'Product Management', 'UI/UX Design', 'Marketing', 'Sales', 'Operations',
  'Finance', 'Legal', 'DevOps', 'Security', 'Mobile Development', 'Web3',
  'Blockchain', 'Fintech', 'Healthtech', 'Edtech', 'E-commerce', 'SaaS'
]

const OFFERS_OPTIONS = [
  'Technical Co-founder', 'Product Management', 'UI/UX Design', 'Marketing',
  'Sales', 'Operations', 'Finance', 'Legal', 'Advisor', 'Fractional CTO',
  'Backend Development', 'Frontend Development', 'Mobile Development',
  'Data Engineering', 'DevOps', 'Security', 'AI/ML', 'Blockchain',
  'Growth Marketing', 'Content Marketing', 'Business Development'
]

const LOOKING_FOR_OPTIONS = [
  'Technical Co-founder', 'Product Management', 'UI/UX Design', 'Marketing',
  'Sales', 'Operations', 'Finance', 'Legal', 'Advisor', 'Fractional CTO',
  'Backend Development', 'Frontend Development', 'Mobile Development',
  'Data Engineering', 'DevOps', 'Security', 'AI/ML', 'Blockchain',
  'Growth Marketing', 'Content Marketing', 'Business Development'
]

const TIMEZONES = [
  'UTC-12:00', 'UTC-11:00', 'UTC-10:00', 'UTC-09:00', 'UTC-08:00', 'UTC-07:00',
  'UTC-06:00', 'UTC-05:00', 'UTC-04:00', 'UTC-03:00', 'UTC-02:00', 'UTC-01:00',
  'UTC+00:00', 'UTC+01:00', 'UTC+02:00', 'UTC+03:00', 'UTC+04:00', 'UTC+05:00',
  'UTC+06:00', 'UTC+07:00', 'UTC+08:00', 'UTC+09:00', 'UTC+10:00', 'UTC+11:00', 'UTC+12:00'
]

interface ProfileData {
  name: string
  email: string
  headline: string
  bio: string
  location: string
  timezone: string
  availability: number
  equityPref: string
  remotePref: string
  languages: string[]
  imageUrl: string
  whatsapp: string
  linkedin: string
  github: string
  skills: string[]
  offers: string[]
  lookingFor: string[]
}

export default function EditProfilePage() {
  const [isLoading, setIsLoading] = useState(false)
  const [profileData, setProfileData] = useState<ProfileData>({
    name: '',
    email: '',
    headline: '',
    bio: '',
    location: '',
    timezone: '',
    availability: 0,
    equityPref: '',
    remotePref: '',
    languages: ['English'],
    imageUrl: '',
    whatsapp: '',
    linkedin: '',
    github: '',
    skills: [],
    offers: [],
    lookingFor: []
  })
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    try {
      const { data: { user }, error } = await supabase.auth.getUser()
      
      if (error || !user) {
        router.push('/auth/signin')
        return
      }

      // Load profile data from API
      const response = await fetch('/api/profile')
      if (response.ok) {
        const profile = await response.json()
        
        // Extract skills from the nested structure
        const skills = profile.skills ? profile.skills.map((s: { skill: { name: string } }) => s.skill.name) : []
        const offers = profile.offers ? profile.offers.map((o: { tag: string }) => o.tag) : []
        const lookingFor = profile.lookingFor ? profile.lookingFor.map((l: { tag: string }) => l.tag) : []
        
        setProfileData({
          name: profile.name || user.user_metadata?.name || '',
          email: user.email || '',
          headline: profile.headline || '',
          bio: profile.bio || '',
          location: profile.location || '',
          timezone: profile.timezone || '',
          availability: profile.availability || 0,
          equityPref: profile.equityPref || '',
          remotePref: profile.remotePref || '',
          languages: profile.languages || ['English'],
          imageUrl: profile.imageUrl || '',
          whatsapp: profile.whatsapp || '',
          linkedin: profile.linkedin || '',
          github: profile.github || '',
          skills,
          offers,
          lookingFor
        })
      }
    } catch (error) {
      console.error('Error loading profile:', error)
      toast.error('Failed to load profile')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      // Transform data to match API expectations
      const updateData = {
        ...profileData,
        skills: profileData.skills.join(', '), // Convert array to comma-separated string
        offers: profileData.offers,
        lookingFor: profileData.lookingFor
      }

      const response = await fetch('/api/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData),
      })

      if (response.ok) {
        toast.success('Profile updated successfully!')
        router.push('/dashboard?tab=profile')
      } else {
        const errorData = await response.json()
        toast.error(errorData.error || 'Failed to update profile')
      }
    } catch (error) {
      console.error('Error updating profile:', error)
      toast.error('Failed to update profile')
    } finally {
      setIsLoading(false)
    }
  }

  const addSkill = (skill: string) => {
    if (!profileData.skills.includes(skill)) {
      setProfileData(prev => ({
        ...prev,
        skills: [...prev.skills, skill]
      }))
    }
  }

  const removeSkill = (skill: string, e?: React.MouseEvent) => {
    e?.preventDefault()
    e?.stopPropagation()
    setProfileData(prev => ({
      ...prev,
      skills: prev.skills.filter(s => s !== skill)
    }))
  }

  const addOffer = (offer: string) => {
    if (!profileData.offers.includes(offer)) {
      setProfileData(prev => ({
        ...prev,
        offers: [...prev.offers, offer]
      }))
    }
  }

  const removeOffer = (offer: string, e?: React.MouseEvent) => {
    e?.preventDefault()
    e?.stopPropagation()
    setProfileData(prev => ({
      ...prev,
      offers: prev.offers.filter(o => o !== offer)
    }))
  }

  const addLookingFor = (lookingFor: string) => {
    if (!profileData.lookingFor.includes(lookingFor)) {
      setProfileData(prev => ({
        ...prev,
        lookingFor: [...prev.lookingFor, lookingFor]
      }))
    }
  }

  const removeLookingFor = (lookingFor: string, e?: React.MouseEvent) => {
    e?.preventDefault()
    e?.stopPropagation()
    setProfileData(prev => ({
      ...prev,
      lookingFor: prev.lookingFor.filter(l => l !== lookingFor)
    }))
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl font-bold">Edit Profile</CardTitle>
            <CardDescription>
              Update your profile information to help others find you
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-8">
              {/* Profile Picture */}
              <ImageUpload
                value={profileData.imageUrl}
                onChange={(value) => setProfileData(prev => ({ ...prev, imageUrl: value as string }))}
                label="Profile Picture"
                className="max-w-xs mx-auto"
              />

              {/* Basic Information */}
              <div className="space-y-6">
                <h3 className="text-lg font-semibold">Basic Information</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Full Name</Label>
                    <Input
                      id="name"
                      value={profileData.name}
                      onChange={(e) => setProfileData(prev => ({ ...prev, name: e.target.value }))}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      value={profileData.email}
                      disabled
                      className="bg-gray-100"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="headline">Professional Headline</Label>
                  <Input
                    id="headline"
                    value={profileData.headline}
                    onChange={(e) => setProfileData(prev => ({ ...prev, headline: e.target.value }))}
                    placeholder="e.g., Full-stack developer with 5+ years in fintech"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="bio">Bio</Label>
                  <Textarea
                    id="bio"
                    value={profileData.bio}
                    onChange={(e) => setProfileData(prev => ({ ...prev, bio: e.target.value }))}
                    placeholder="Tell us about yourself, your experience, and what you're passionate about..."
                    rows={4}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="location">Location</Label>
                    <Input
                      id="location"
                      value={profileData.location}
                      onChange={(e) => setProfileData(prev => ({ ...prev, location: e.target.value }))}
                      placeholder="San Francisco, CA"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="whatsapp">WhatsApp Number</Label>
                    <Input
                      id="whatsapp"
                      value={profileData.whatsapp}
                      onChange={(e) => setProfileData(prev => ({ ...prev, whatsapp: e.target.value }))}
                      placeholder="+1234567890"
                    />
                  </div>
                </div>
              </div>

              {/* Skills & Expertise */}
              <div className="space-y-6">
                <h3 className="text-lg font-semibold">Skills & Expertise</h3>
                
                <div className="space-y-2">
                  <Label>Skills</Label>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {profileData.skills.map((skill) => (
                      <div key={skill} className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-secondary text-secondary-foreground">
                        {skill}
                        <button
                          type="button"
                          className="ml-1 h-3 w-3 rounded-full hover:bg-secondary-foreground/20 flex items-center justify-center"
                          onClick={(e) => removeSkill(skill, e)}
                        >
                          <X className="h-2 w-2" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start">
                        <Plus className="mr-2 h-4 w-4" />
                        Add skills
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-full p-0">
                      <Command>
                        <CommandInput placeholder="Search skills..." />
                        <CommandEmpty>No skills found.</CommandEmpty>
                        <CommandGroup>
                          {SKILLS_OPTIONS.map((skill) => (
                            <CommandItem
                              key={skill}
                              onSelect={() => addSkill(skill)}
                              className={cn(
                                profileData.skills.includes(skill) && "opacity-50"
                              )}
                            >
                              <Check
                                className={cn(
                                  "mr-2 h-4 w-4",
                                  profileData.skills.includes(skill) ? "opacity-100" : "opacity-0"
                                )}
                              />
                              {skill}
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </Command>
                    </PopoverContent>
                  </Popover>
                </div>

                <div className="space-y-2">
                  <Label>What you offer</Label>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {profileData.offers.map((offer) => (
                      <div key={offer} className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border border-input bg-background hover:bg-accent hover:text-accent-foreground">
                        {offer}
                        <button
                          type="button"
                          className="ml-1 h-3 w-3 rounded-full hover:bg-accent-foreground/20 flex items-center justify-center"
                          onClick={(e) => removeOffer(offer, e)}
                        >
                          <X className="h-2 w-2" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start">
                        <Plus className="mr-2 h-4 w-4" />
                        Add offers
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-full p-0">
                      <Command>
                        <CommandInput placeholder="Search offers..." />
                        <CommandEmpty>No offers found.</CommandEmpty>
                        <CommandGroup>
                          {OFFERS_OPTIONS.map((offer) => (
                            <CommandItem
                              key={offer}
                              onSelect={() => addOffer(offer)}
                              className={cn(
                                profileData.offers.includes(offer) && "opacity-50"
                              )}
                            >
                              <Check
                                className={cn(
                                  "mr-2 h-4 w-4",
                                  profileData.offers.includes(offer) ? "opacity-100" : "opacity-0"
                                )}
                              />
                              {offer}
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </Command>
                    </PopoverContent>
                  </Popover>
                </div>

                <div className="space-y-2">
                  <Label>What you&apos;re looking for</Label>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {profileData.lookingFor.map((lookingFor) => (
                      <div key={lookingFor} className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/80">
                        {lookingFor}
                        <button
                          type="button"
                          className="ml-1 h-3 w-3 rounded-full hover:bg-primary-foreground/20 flex items-center justify-center"
                          onClick={(e) => removeLookingFor(lookingFor, e)}
                        >
                          <X className="h-2 w-2" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start">
                        <Plus className="mr-2 h-4 w-4" />
                        Add looking for
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-full p-0">
                      <Command>
                        <CommandInput placeholder="Search looking for..." />
                        <CommandEmpty>No options found.</CommandEmpty>
                        <CommandGroup>
                          {LOOKING_FOR_OPTIONS.map((lookingFor) => (
                            <CommandItem
                              key={lookingFor}
                              onSelect={() => addLookingFor(lookingFor)}
                              className={cn(
                                profileData.lookingFor.includes(lookingFor) && "opacity-50"
                              )}
                            >
                              <Check
                                className={cn(
                                  "mr-2 h-4 w-4",
                                  profileData.lookingFor.includes(lookingFor) ? "opacity-100" : "opacity-0"
                                )}
                              />
                              {lookingFor}
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </Command>
                    </PopoverContent>
                  </Popover>
                </div>
              </div>

              {/* Work Preferences */}
              <div className="space-y-6">
                <h3 className="text-lg font-semibold">Work Preferences</h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="timezone">Timezone</Label>
                    <Select
                      value={profileData.timezone}
                      onValueChange={(value) => setProfileData(prev => ({ ...prev, timezone: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select your timezone" />
                      </SelectTrigger>
                      <SelectContent>
                        {TIMEZONES.map((tz) => (
                          <SelectItem key={tz} value={tz}>
                            {tz}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="availability">Availability (% of time)</Label>
                    <Input
                      id="availability"
                      type="number"
                      min="0"
                      max="100"
                      value={profileData.availability}
                      onChange={(e) => setProfileData(prev => ({ ...prev, availability: parseInt(e.target.value) || 0 }))}
                      placeholder="80"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="equityPref">Equity Preference</Label>
                    <Select
                      value={profileData.equityPref}
                      onValueChange={(value) => setProfileData(prev => ({ ...prev, equityPref: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select preference" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="equity">Equity only</SelectItem>
                        <SelectItem value="cash">Cash only</SelectItem>
                        <SelectItem value="both">Both equity and cash</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="remotePref">Remote Preference</Label>
                    <Select
                      value={profileData.remotePref}
                      onValueChange={(value) => setProfileData(prev => ({ ...prev, remotePref: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select preference" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="remote">Remote</SelectItem>
                        <SelectItem value="hybrid">Hybrid</SelectItem>
                        <SelectItem value="onsite">Onsite</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              {/* Social Links */}
              <div className="space-y-6">
                <h3 className="text-lg font-semibold">Social Links</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="linkedin">LinkedIn URL</Label>
                    <Input
                      id="linkedin"
                      type="url"
                      value={profileData.linkedin}
                      onChange={(e) => setProfileData(prev => ({ ...prev, linkedin: e.target.value }))}
                      placeholder="https://linkedin.com/in/yourprofile"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="github">GitHub URL</Label>
                    <Input
                      id="github"
                      type="url"
                      value={profileData.github}
                      onChange={(e) => setProfileData(prev => ({ ...prev, github: e.target.value }))}
                      placeholder="https://github.com/yourusername"
                    />
                  </div>
                </div>
              </div>

              <div className="flex gap-4">
                <Button type="submit" disabled={isLoading} className="flex-1">
                  {isLoading ? 'Saving...' : 'Save Changes'}
                </Button>
                <Button 
                  type="button" 
                  variant="outline" 
                  onClick={() => router.push('/dashboard?tab=profile')}
                  className="flex-1"
                >
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
