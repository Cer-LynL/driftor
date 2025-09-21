import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ userId: string }> }
) {
  try {
    const supabase = await createClient()
    const { data: { user }, error } = await supabase.auth.getUser()

    if (error || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const { userId } = await params

    // Fetch the user profile with all related data
    const profile = await prisma.user.findUnique({
      where: { id: userId },
      include: {
        skills: {
          include: {
            skill: true
          }
        },
        offers: true,
        lookingFor: true,
        startups: {
          orderBy: {
            createdAt: 'desc'
          }
        }
      }
    })

    if (!profile) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 })
    }

    // Don't return sensitive information like email for other users
    const publicProfile = {
      id: profile.id,
      name: profile.name,
      headline: profile.headline,
      bio: profile.bio,
      location: profile.location,
      timezone: profile.timezone,
      availability: profile.availability,
      equityPref: profile.equityPref,
      remotePref: profile.remotePref,
      languages: profile.languages,
      imageUrl: profile.imageUrl,
      whatsapp: profile.whatsapp,
      linkedin: profile.linkedin,
      github: profile.github,
      skills: profile.skills,
      offers: profile.offers,
      lookingFor: profile.lookingFor,
      startups: profile.startups
    }

    return NextResponse.json(publicProfile)
  } catch (error) {
    console.error('Error fetching user profile:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
