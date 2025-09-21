'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
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
import { Check, ChevronsUpDown, Plus, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { onboardingSchema, type OnboardingInput } from '@/lib/validations/profile'
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

export default function OnboardingPage() {
  const [currentStep, setCurrentStep] = useState(1)
  const [isLoading, setIsLoading] = useState(false)
  const [formData, setFormData] = useState<Partial<OnboardingInput>>({
    skills: [],
    offers: [],
    lookingFor: [],
    languages: ['English'],
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const router = useRouter()
  const supabase = createClient()

  const totalSteps = 4

  const handleNext = () => {
    if (currentStep < totalSteps) {
      setCurrentStep(currentStep + 1)
    }
  }

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleSubmit = async () => {
    setIsLoading(true)
    setErrors({})

    try {
      const validatedData = onboardingSchema.parse(formData)
      
      // Transform the data to match the profile API schema
      const profileData = {
        name: validatedData.name,
        headline: validatedData.headline,
        bio: validatedData.bio,
        location: validatedData.location,
        timezone: validatedData.timezone,
        availability: validatedData.availability,
        equityPref: validatedData.equityPref,
        remotePref: validatedData.remotePref,
        languages: validatedData.languages,
        imageUrl: formData.imageUrl,
        whatsapp: formData.whatsapp,
        // Convert arrays to comma-separated strings for the profile API
        skills: validatedData.skills.join(', '),
        offers: validatedData.offers,
        lookingFor: validatedData.lookingFor,
      }

      // Save the profile data to the database
      const response = await fetch('/api/profile', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(profileData),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to create profile')
      }

      toast.success('Profile created successfully!')
      router.push('/dashboard')
    } catch (error) {
      if (error instanceof Error) {
        toast.error(error.message)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const addSkill = (skill: string) => {
    if (!formData.skills?.includes(skill)) {
      setFormData({
        ...formData,
        skills: [...(formData.skills || []), skill]
      })
    }
  }

  const removeSkill = (skill: string) => {
    setFormData({
      ...formData,
      skills: formData.skills?.filter(s => s !== skill) || []
    })
  }

  const addOffer = (offer: string) => {
    if (!formData.offers?.includes(offer)) {
      setFormData({
        ...formData,
        offers: [...(formData.offers || []), offer]
      })
    }
  }

  const removeOffer = (offer: string) => {
    setFormData({
      ...formData,
      offers: formData.offers?.filter(o => o !== offer) || []
    })
  }

  const addLookingFor = (lookingFor: string) => {
    if (!formData.lookingFor?.includes(lookingFor)) {
      setFormData({
        ...formData,
        lookingFor: [...(formData.lookingFor || []), lookingFor]
      })
    }
  }

  const removeLookingFor = (lookingFor: string) => {
    setFormData({
      ...formData,
      lookingFor: formData.lookingFor?.filter(l => l !== lookingFor) || []
    })
  }

  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-6">
            <ImageUpload
              value={formData.imageUrl || ''}
              onChange={(value) => setFormData({ ...formData, imageUrl: value as string })}
              label="Profile Picture"
              className="max-w-xs mx-auto"
            />

            <div className="space-y-2">
              <Label htmlFor="name">Full Name</Label>
              <Input
                id="name"
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="John Doe"
              />
              {errors.name && <p className="text-sm text-red-500">{errors.name}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="headline">Professional Headline</Label>
              <Input
                id="headline"
                value={formData.headline || ''}
                onChange={(e) => setFormData({ ...formData, headline: e.target.value })}
                placeholder="e.g., Full-stack developer with 5+ years in fintech"
              />
              {errors.headline && <p className="text-sm text-red-500">{errors.headline}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="bio">Bio</Label>
              <Textarea
                id="bio"
                value={formData.bio || ''}
                onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
                placeholder="Tell us about yourself, your experience, and what you're passionate about..."
                rows={4}
              />
              {errors.bio && <p className="text-sm text-red-500">{errors.bio}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="location">Location</Label>
              <Input
                id="location"
                value={formData.location || ''}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                placeholder="San Francisco, CA"
              />
              {errors.location && <p className="text-sm text-red-500">{errors.location}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="whatsapp">WhatsApp Number (Optional)</Label>
              <Input
                id="whatsapp"
                value={formData.whatsapp || ''}
                onChange={(e) => setFormData({ ...formData, whatsapp: e.target.value })}
                placeholder="+1234567890"
              />
              <p className="text-xs text-gray-500">
                This will allow other users to contact you directly via WhatsApp
              </p>
            </div>
          </div>
        )

      case 2:
        return (
          <div className="space-y-6">
            <div className="space-y-2">
              <Label>Skills</Label>
              <div className="flex flex-wrap gap-2 mb-2">
                {formData.skills?.map((skill) => (
                  <Badge key={skill} variant="secondary" className="flex items-center gap-1">
                    {skill}
                    <X
                      className="h-3 w-3 cursor-pointer"
                      onClick={() => removeSkill(skill)}
                    />
                  </Badge>
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
                            formData.skills?.includes(skill) && "opacity-50"
                          )}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              formData.skills?.includes(skill) ? "opacity-100" : "opacity-0"
                            )}
                          />
                          {skill}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </Command>
                </PopoverContent>
              </Popover>
              {errors.skills && <p className="text-sm text-red-500">{errors.skills}</p>}
            </div>

            <div className="space-y-2">
              <Label>What you offer</Label>
              <div className="flex flex-wrap gap-2 mb-2">
                {formData.offers?.map((offer) => (
                  <Badge key={offer} variant="secondary" className="flex items-center gap-1">
                    {offer}
                    <X
                      className="h-3 w-3 cursor-pointer"
                      onClick={() => removeOffer(offer)}
                    />
                  </Badge>
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
                            formData.offers?.includes(offer) && "opacity-50"
                          )}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              formData.offers?.includes(offer) ? "opacity-100" : "opacity-0"
                            )}
                          />
                          {offer}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </Command>
                </PopoverContent>
              </Popover>
              {errors.offers && <p className="text-sm text-red-500">{errors.offers}</p>}
            </div>

            <div className="space-y-2">
              <Label>What you&apos;re looking for</Label>
              <div className="flex flex-wrap gap-2 mb-2">
                {formData.lookingFor?.map((lookingFor) => (
                  <Badge key={lookingFor} variant="secondary" className="flex items-center gap-1">
                    {lookingFor}
                    <X
                      className="h-3 w-3 cursor-pointer"
                      onClick={() => removeLookingFor(lookingFor)}
                    />
                  </Badge>
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
                            formData.lookingFor?.includes(lookingFor) && "opacity-50"
                          )}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              formData.lookingFor?.includes(lookingFor) ? "opacity-100" : "opacity-0"
                            )}
                          />
                          {lookingFor}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </Command>
                </PopoverContent>
              </Popover>
              {errors.lookingFor && <p className="text-sm text-red-500">{errors.lookingFor}</p>}
            </div>
          </div>
        )

      case 3:
        return (
          <div className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Select
                value={formData.timezone || ''}
                onValueChange={(value) => setFormData({ ...formData, timezone: value })}
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
              {errors.timezone && <p className="text-sm text-red-500">{errors.timezone}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="availability">Availability (% of time)</Label>
              <Input
                id="availability"
                type="number"
                min="0"
                max="100"
                value={formData.availability || ''}
                onChange={(e) => setFormData({ ...formData, availability: parseInt(e.target.value) })}
                placeholder="80"
              />
              {errors.availability && <p className="text-sm text-red-500">{errors.availability}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="equityPref">Equity Preference</Label>
              <Select
                value={formData.equityPref || ''}
                onValueChange={(value) => setFormData({ ...formData, equityPref: value as 'equity' | 'cash' | 'both' })}
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
              {errors.equityPref && <p className="text-sm text-red-500">{errors.equityPref}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="remotePref">Remote Preference</Label>
              <Select
                value={formData.remotePref || ''}
                onValueChange={(value) => setFormData({ ...formData, remotePref: value as 'remote' | 'hybrid' | 'onsite' })}
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
              {errors.remotePref && <p className="text-sm text-red-500">{errors.remotePref}</p>}
            </div>
          </div>
        )

      case 4:
        return (
          <div className="space-y-6">
            <div className="text-center">
              <h3 className="text-lg font-semibold">Review your profile</h3>
              <p className="text-gray-500">Make sure everything looks good before we create your profile.</p>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>{formData.name}</CardTitle>
                <CardDescription>{formData.headline}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm">{formData.bio}</p>
                <div className="text-sm text-gray-500">
                  <p><strong>Location:</strong> {formData.location}</p>
                  <p><strong>Timezone:</strong> {formData.timezone}</p>
                  <p><strong>Availability:</strong> {formData.availability}%</p>
                  <p><strong>Equity Preference:</strong> {formData.equityPref}</p>
                  <p><strong>Remote Preference:</strong> {formData.remotePref}</p>
                </div>
                <div className="space-y-2">
                  <div>
                    <strong className="text-sm">Skills:</strong>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {formData.skills?.map((skill) => (
                        <Badge key={skill} variant="secondary" className="text-xs">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <strong className="text-sm">Offers:</strong>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {formData.offers?.map((offer) => (
                        <Badge key={offer} variant="outline" className="text-xs">
                          {offer}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <strong className="text-sm">Looking for:</strong>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {formData.lookingFor?.map((lookingFor) => (
                        <Badge key={lookingFor} variant="outline" className="text-xs">
                          {lookingFor}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Complete your profile</CardTitle>
              <CardDescription>
                Step {currentStep} of {totalSteps}
              </CardDescription>
            </div>
            <div className="flex space-x-2">
              {Array.from({ length: totalSteps }, (_, i) => (
                <div
                  key={i}
                  className={cn(
                    "w-2 h-2 rounded-full",
                    i + 1 <= currentStep ? "bg-blue-500" : "bg-gray-200"
                  )}
                />
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {renderStep()}
          
          <div className="flex justify-between mt-8">
            <Button
              variant="outline"
              onClick={handleBack}
              disabled={currentStep === 1}
            >
              Back
            </Button>
            
            {currentStep < totalSteps ? (
              <Button onClick={handleNext}>
                Next
              </Button>
            ) : (
              <Button onClick={handleSubmit} disabled={isLoading}>
                {isLoading ? 'Creating profile...' : 'Complete'}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
