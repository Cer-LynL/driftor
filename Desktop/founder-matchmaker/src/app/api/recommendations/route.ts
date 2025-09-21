import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'

export async function GET(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { data: { user }, error } = await supabase.auth.getUser()

    if (error || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    // Get current user's profile
    const currentUser = await prisma.user.findUnique({
      where: { id: user.id },
      include: {
        skills: {
          include: {
            skill: true
          }
        },
        offers: true,
        lookingFor: true,
        likesSent: true
      }
    })

    if (!currentUser) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 })
    }

    // Get users that the current user hasn't liked yet
    const likedUserIds = currentUser.likesSent.map(like => like.toId)

    // Find potential matches
    const recommendations = await prisma.user.findMany({
      where: {
        id: {
          not: user.id,
          notIn: likedUserIds
        }
      },
      include: {
        skills: {
          include: {
            skill: true
          }
        },
        offers: true,
        lookingFor: true,
        startups: true
      },
      take: 20
    })

    // Calculate match scores
    const scoredRecommendations = recommendations.map(recommendation => {
      const score = calculateMatchScore(currentUser, recommendation)
      return {
        ...recommendation,
        matchScore: score.score,
        matchReasons: score.reasons
      }
    })

    // Sort by match score
    scoredRecommendations.sort((a, b) => b.matchScore - a.matchScore)

    return NextResponse.json(scoredRecommendations)
  } catch (error) {
    console.error('Error fetching recommendations:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

interface UserWithRelations {
  offers: Array<{ tag: string }>
  lookingFor: Array<{ tag: string }>
  skills: Array<{ skill: { name: string } }>
  location?: string
  availability?: number
  bio?: string
  headline?: string
}

function calculateMatchScore(user1: UserWithRelations, user2: UserWithRelations) {
  let score = 0
  const reasons: string[] = []

  // Tag overlap (40 points max)
  const user1Offers = user1.offers.map((o) => o.tag)
  const user1LookingFor = user1.lookingFor.map((l) => l.tag)
  const user2Offers = user2.offers.map((o) => o.tag)
  const user2LookingFor = user2.lookingFor.map((l) => l.tag)

  const offerOverlap = user1Offers.filter((offer: string) => 
    user2LookingFor.includes(offer)
  ).length

  const lookingForOverlap = user1LookingFor.filter((lookingFor: string) => 
    user2Offers.includes(lookingFor)
  ).length

  const tagScore = Math.min(40, (offerOverlap + lookingForOverlap) * 8)
  score += tagScore

  if (offerOverlap > 0) {
    reasons.push(`${offerOverlap} matching skills/offers`)
  }

  // Skill proximity (20 points max)
  const user1Skills = user1.skills.map((s) => s.skill.name)
  const user2Skills = user2.skills.map((s) => s.skill.name)
  const skillOverlap = user1Skills.filter((skill: string) => 
    user2Skills.includes(skill)
  ).length

  const skillScore = Math.min(20, skillOverlap * 4)
  score += skillScore

  if (skillOverlap > 0) {
    reasons.push(`${skillOverlap} shared skills`)
  }

  // Location proximity (10 points max)
  if (user1.location && user2.location) {
    // Simple location matching - in real app, use geolocation
    const locationScore = user1.location === user2.location ? 10 : 5
    score += locationScore
    if (locationScore === 10) {
      reasons.push('Same location')
    }
  }

  // Availability alignment (10 points max)
  if (user1.availability && user2.availability) {
    const availabilityDiff = Math.abs(user1.availability - user2.availability)
    const availabilityScore = Math.max(0, 10 - availabilityDiff / 10)
    score += availabilityScore
    if (availabilityScore > 7) {
      reasons.push('Similar availability')
    }
  }

  // Profile completeness (5 points max)
  const user2Completeness = [
    user2.bio,
    user2.headline,
    user2.location,
    user2.skills.length > 0,
    user2.offers.length > 0,
    user2.lookingFor.length > 0
  ].filter(Boolean).length

  const completenessScore = (user2Completeness / 6) * 5
  score += completenessScore

  if (completenessScore > 4) {
    reasons.push('Complete profile')
  }

  return {
    score: Math.round(score),
    reasons: reasons.slice(0, 3) // Top 3 reasons
  }
}
