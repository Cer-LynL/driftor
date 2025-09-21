'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
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
import { startupSchema, type StartupInput } from '@/lib/validations/profile'
import { toast } from 'sonner'
import { ImageUpload } from '@/components/ui/image-upload'

const MARKET_OPTIONS = [
  'Fintech', 'Healthtech', 'Edtech', 'E-commerce', 'SaaS', 'B2B', 'B2C',
  'AI/ML', 'Blockchain', 'Web3', 'Mobile', 'Enterprise', 'Consumer',
  'Real Estate', 'Travel', 'Food & Beverage', 'Fashion', 'Gaming',
  'Media & Entertainment', 'Transportation', 'Energy', 'Agriculture'
]

const STAGE_OPTIONS = [
  { value: 'idea', label: 'Idea Stage' },
  { value: 'prototype', label: 'Prototype' },
  { value: 'MVP', label: 'MVP' },
  { value: 'beta', label: 'Beta' },
  { value: 'revenue', label: 'Revenue' },
  { value: 'growth', label: 'Growth' }
]

interface StartupData extends StartupInput {
  id: string
  createdAt: string
  updatedAt: string
}

export default function EditStartupPage() {
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingData, setIsLoadingData] = useState(true)
  const [formData, setFormData] = useState<Partial<StartupInput>>({
    markets: [],
    hiringNeeds: [],
    keywords: [],
    imageUrls: []
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const router = useRouter()
  const params = useParams()
  const startupId = params.id as string

  useEffect(() => {
    if (startupId) {
      loadStartupData()
    }
  }, [startupId])

  const loadStartupData = async () => {
    setIsLoadingData(true)
    try {
      const response = await fetch(`/api/startups/${startupId}`)
      if (response.ok) {
        const startup: StartupData = await response.json()
        setFormData({
          name: startup.name,
          oneLiner: startup.oneLiner,
          stage: startup.stage,
          markets: startup.markets || [],
          problem: startup.problem,
          solution: startup.solution,
          plan: startup.plan,
          logoUrl: startup.logoUrl,
          imageUrls: startup.imageUrls || [],
          websiteUrl: startup.websiteUrl,
          demoUrl: startup.demoUrl,
          deckUrl: startup.deckUrl,
          teamSize: startup.teamSize,
          hiringNeeds: startup.hiringNeeds || [],
          keywords: startup.keywords || []
        })
      } else {
        toast.error('Failed to load startup data')
        router.push('/dashboard?tab=profile')
      }
    } catch (error) {
      console.error('Error loading startup:', error)
      toast.error('Failed to load startup data')
      router.push('/dashboard?tab=profile')
    } finally {
      setIsLoadingData(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setErrors({})

    try {
      // Transform null values to empty strings for URL fields
      const cleanedFormData = {
        ...formData,
        logoUrl: formData.logoUrl || '',
        websiteUrl: formData.websiteUrl || '',
        demoUrl: formData.demoUrl || '',
        deckUrl: formData.deckUrl || '',
      }
      
      const validatedData = startupSchema.parse(cleanedFormData)
      
      const response = await fetch(`/api/startups/${startupId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(validatedData)
      })

      if (response.ok) {
        toast.success('Startup updated successfully!')
        router.push('/dashboard?tab=profile')
      } else {
        const error = await response.json()
        toast.error(error.error || 'Failed to update startup')
      }
    } catch (error) {
      if (error instanceof Error) {
        toast.error(error.message)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this startup? This action cannot be undone.')) {
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch(`/api/startups/${startupId}`, {
        method: 'DELETE'
      })

      if (response.ok) {
        toast.success('Startup deleted successfully!')
        router.push('/dashboard?tab=profile')
      } else {
        const error = await response.json()
        toast.error(error.error || 'Failed to delete startup')
      }
    } catch (error) {
      console.error('Error deleting startup:', error)
      toast.error('Failed to delete startup')
    } finally {
      setIsLoading(false)
    }
  }

  const addMarket = (market: string) => {
    if (!formData.markets?.includes(market)) {
      setFormData({
        ...formData,
        markets: [...(formData.markets || []), market]
      })
    }
  }

  const removeMarket = (market: string) => {
    setFormData({
      ...formData,
      markets: formData.markets?.filter(m => m !== market) || []
    })
  }

  const addHiringNeed = (need: string) => {
    if (!formData.hiringNeeds?.includes(need)) {
      setFormData({
        ...formData,
        hiringNeeds: [...(formData.hiringNeeds || []), need]
      })
    }
  }

  const removeHiringNeed = (need: string) => {
    setFormData({
      ...formData,
      hiringNeeds: formData.hiringNeeds?.filter(h => h !== need) || []
    })
  }

  const addKeyword = (keyword: string) => {
    if (!formData.keywords?.includes(keyword)) {
      setFormData({
        ...formData,
        keywords: [...(formData.keywords || []), keyword]
      })
    }
  }

  const removeKeyword = (keyword: string) => {
    setFormData({
      ...formData,
      keywords: formData.keywords?.filter(k => k !== keyword) || []
    })
  }

  if (isLoadingData) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-center py-12">
            <div className="text-gray-500">Loading startup data...</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <Card>
          <CardHeader>
            <CardTitle>Edit Startup Profile</CardTitle>
            <CardDescription>
              Update your startup information
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="name">Startup Name</Label>
                <Input
                  id="name"
                  value={formData.name || ''}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="My Awesome Startup"
                  required
                />
                {errors.name && <p className="text-sm text-red-500">{errors.name}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="oneLiner">One-liner Description</Label>
                <Input
                  id="oneLiner"
                  value={formData.oneLiner || ''}
                  onChange={(e) => setFormData({ ...formData, oneLiner: e.target.value })}
                  placeholder="We're building the future of..."
                  required
                />
                {errors.oneLiner && <p className="text-sm text-red-500">{errors.oneLiner}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="stage">Current Stage</Label>
                <Select
                  value={formData.stage || ''}
                  onValueChange={(value) => setFormData({ ...formData, stage: value as 'idea' | 'prototype' | 'MVP' | 'beta' | 'revenue' | 'growth' })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select stage" />
                  </SelectTrigger>
                  <SelectContent>
                    {STAGE_OPTIONS.map((stage) => (
                      <SelectItem key={stage.value} value={stage.value}>
                        {stage.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.stage && <p className="text-sm text-red-500">{errors.stage}</p>}
              </div>

              <div className="space-y-2">
                <Label>Target Markets</Label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {formData.markets?.map((market) => (
                    <Badge key={market} variant="secondary" className="flex items-center gap-1">
                      {market}
                      <X
                        className="h-3 w-3 cursor-pointer"
                        onClick={() => removeMarket(market)}
                      />
                    </Badge>
                  ))}
                </div>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="outline" className="w-full justify-start">
                      <Plus className="mr-2 h-4 w-4" />
                      Add markets
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-full p-0">
                    <Command>
                      <CommandInput placeholder="Search markets..." />
                      <CommandEmpty>No markets found.</CommandEmpty>
                      <CommandGroup>
                        {MARKET_OPTIONS.map((market) => (
                          <CommandItem
                            key={market}
                            onSelect={() => addMarket(market)}
                            className={cn(
                              formData.markets?.includes(market) && "opacity-50"
                            )}
                          >
                            <Check
                              className={cn(
                                "mr-2 h-4 w-4",
                                formData.markets?.includes(market) ? "opacity-100" : "opacity-0"
                              )}
                            />
                            {market}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </Command>
                  </PopoverContent>
                </Popover>
                {errors.markets && <p className="text-sm text-red-500">{errors.markets}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="problem">Problem Statement</Label>
                <Textarea
                  id="problem"
                  value={formData.problem || ''}
                  onChange={(e) => setFormData({ ...formData, problem: e.target.value })}
                  placeholder="What problem are you solving?"
                  rows={3}
                />
                {errors.problem && <p className="text-sm text-red-500">{errors.problem}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="solution">Solution</Label>
                <Textarea
                  id="solution"
                  value={formData.solution || ''}
                  onChange={(e) => setFormData({ ...formData, solution: e.target.value })}
                  placeholder="How are you solving this problem?"
                  rows={3}
                />
                {errors.solution && <p className="text-sm text-red-500">{errors.solution}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="plan">Business Plan / Roadmap</Label>
                <Textarea
                  id="plan"
                  value={formData.plan || ''}
                  onChange={(e) => setFormData({ ...formData, plan: e.target.value })}
                  placeholder="What's your plan for the next 6-12 months?"
                  rows={4}
                />
                {errors.plan && <p className="text-sm text-red-500">{errors.plan}</p>}
              </div>

              {/* Logo Upload */}
              <div className="space-y-2">
                <Label>Startup Logo (Optional)</Label>
                <ImageUpload
                  value={formData.logoUrl || ''}
                  onChange={(value) => setFormData({ ...formData, logoUrl: value as string })}
                  label="Upload Logo"
                  className="max-w-xs"
                />
                {errors.logoUrl && <p className="text-sm text-red-500">{errors.logoUrl}</p>}
              </div>

              {/* Website and Demo URLs */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="websiteUrl">Website URL (Optional)</Label>
                  <Input
                    id="websiteUrl"
                    type="url"
                    value={formData.websiteUrl || ''}
                    onChange={(e) => setFormData({ ...formData, websiteUrl: e.target.value })}
                    placeholder="https://yourstartup.com"
                  />
                  {errors.websiteUrl && <p className="text-sm text-red-500">{errors.websiteUrl}</p>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="demoUrl">Demo URL (Optional)</Label>
                  <Input
                    id="demoUrl"
                    type="url"
                    value={formData.demoUrl || ''}
                    onChange={(e) => setFormData({ ...formData, demoUrl: e.target.value })}
                    placeholder="https://demo.yourstartup.com"
                  />
                  {errors.demoUrl && <p className="text-sm text-red-500">{errors.demoUrl}</p>}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="deckUrl">Pitch Deck URL (Optional)</Label>
                <Input
                  id="deckUrl"
                  type="url"
                  value={formData.deckUrl || ''}
                  onChange={(e) => setFormData({ ...formData, deckUrl: e.target.value })}
                  placeholder="https://example.com/pitch-deck"
                />
                {errors.deckUrl && <p className="text-sm text-red-500">{errors.deckUrl}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="teamSize">Current Team Size</Label>
                <Input
                  id="teamSize"
                  type="number"
                  min="1"
                  value={formData.teamSize || ''}
                  onChange={(e) => setFormData({ ...formData, teamSize: parseInt(e.target.value) })}
                  placeholder="2"
                />
                {errors.teamSize && <p className="text-sm text-red-500">{errors.teamSize}</p>}
              </div>

              <div className="space-y-2">
                <Label>Hiring Needs</Label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {formData.hiringNeeds?.map((need) => (
                    <Badge key={need} variant="secondary" className="flex items-center gap-1">
                      {need}
                      <X
                        className="h-3 w-3 cursor-pointer"
                        onClick={() => removeHiringNeed(need)}
                      />
                    </Badge>
                  ))}
                </div>
                <Input
                  placeholder="Type and press Enter to add hiring needs"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      const value = e.currentTarget.value.trim()
                      if (value) {
                        addHiringNeed(value)
                        e.currentTarget.value = ''
                      }
                    }
                  }}
                />
                {errors.hiringNeeds && <p className="text-sm text-red-500">{errors.hiringNeeds}</p>}
              </div>

              <div className="space-y-2">
                <Label>Keywords</Label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {formData.keywords?.map((keyword) => (
                    <Badge key={keyword} variant="outline" className="flex items-center gap-1">
                      {keyword}
                      <X
                        className="h-3 w-3 cursor-pointer"
                        onClick={() => removeKeyword(keyword)}
                      />
                    </Badge>
                  ))}
                </div>
                <Input
                  placeholder="Type and press Enter to add keywords"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      const value = e.currentTarget.value.trim()
                      if (value) {
                        addKeyword(value)
                        e.currentTarget.value = ''
                      }
                    }
                  }}
                />
                {errors.keywords && <p className="text-sm text-red-500">{errors.keywords}</p>}
              </div>

              <div className="flex justify-between">
                <Button 
                  type="button" 
                  variant="destructive" 
                  onClick={handleDelete}
                  disabled={isLoading}
                >
                  Delete Startup
                </Button>
                <div className="flex space-x-4">
                  <Button type="button" variant="outline" onClick={() => router.back()}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={isLoading}>
                    {isLoading ? 'Saving...' : 'Save Changes'}
                  </Button>
                </div>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
