import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'
import { profileSchema } from '@/lib/validations/profile'

export async function GET(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { data: { user }, error } = await supabase.auth.getUser()

    if (error || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const profile = await prisma.user.findUnique({
      where: { id: user.id },
      include: {
        skills: {
          include: {
            skill: true
          }
        },
        offers: true,
        lookingFor: true,
        startups: true
      }
    })

    if (!profile) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 })
    }

    return NextResponse.json(profile)
  } catch (error) {
    console.error('Error fetching profile:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { data: { user }, error } = await supabase.auth.getUser()

    if (error || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await request.json()
    const validatedData = profileSchema.parse(body)

    // Extract skills, offers, and lookingFor from the validated data
    const { skills, offers, lookingFor, ...userData } = validatedData

    // Create or update the user profile
    const profile = await prisma.user.upsert({
      where: { id: user.id },
      update: userData,
      create: {
        id: user.id,
        email: user.email!,
        ...userData
      }
    })

    // Handle skills (many-to-many through SkillOnUser)
    if (skills) {
      // Delete existing skills
      await prisma.skillOnUser.deleteMany({
        where: { userId: user.id }
      })

      // Parse skills from comma-separated string
      const skillNames = skills.split(',').map(s => s.trim()).filter(s => s.length > 0)
      
      for (const skillName of skillNames) {
        // Create skill if it doesn't exist
        const skill = await prisma.skill.upsert({
          where: { name: skillName },
          update: {},
          create: { name: skillName }
        })

        // Create the relationship
        await prisma.skillOnUser.create({
          data: {
            userId: user.id,
            skillId: skill.id
          }
        })
      }
    }

    // Handle offers
    if (offers) {
      // Delete existing offers
      await prisma.offer.deleteMany({
        where: { userId: user.id }
      })

      // Parse offers from array or comma-separated string
      const offerTags = Array.isArray(offers) ? offers : offers.split(',').map(s => s.trim()).filter(s => s.length > 0)
      
      for (const tag of offerTags) {
        await prisma.offer.create({
          data: {
            userId: user.id,
            tag: tag
          }
        })
      }
    }

    // Handle lookingFor
    if (lookingFor) {
      // Delete existing lookingFor
      await prisma.lookingFor.deleteMany({
        where: { userId: user.id }
      })

      // Parse lookingFor from array or comma-separated string
      const lookingForTags = Array.isArray(lookingFor) ? lookingFor : lookingFor.split(',').map(s => s.trim()).filter(s => s.length > 0)
      
      for (const tag of lookingForTags) {
        await prisma.lookingFor.create({
          data: {
            userId: user.id,
            tag: tag
          }
        })
      }
    }

    // Fetch the complete profile with relations
    const completeProfile = await prisma.user.findUnique({
      where: { id: user.id },
      include: {
        skills: {
          include: {
            skill: true
          }
        },
        offers: true,
        lookingFor: true,
        startups: true
      }
    })

    return NextResponse.json(completeProfile)
  } catch (error) {
    console.error('Error creating/updating profile:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

export async function PUT(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { data: { user }, error } = await supabase.auth.getUser()

    if (error || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await request.json()
    const validatedData = profileSchema.parse(body)

    // Extract skills, offers, and lookingFor from the validated data
    const { skills, offers, lookingFor, ...userData } = validatedData

    // Create or update the user profile
    const profile = await prisma.user.upsert({
      where: { id: user.id },
      update: userData,
      create: {
        id: user.id,
        email: user.email!,
        ...userData
      }
    })

    // Handle skills (many-to-many through SkillOnUser)
    if (skills) {
      // Delete existing skills
      await prisma.skillOnUser.deleteMany({
        where: { userId: user.id }
      })

      // Parse skills from comma-separated string
      const skillNames = skills.split(',').map(s => s.trim()).filter(s => s.length > 0)
      
      for (const skillName of skillNames) {
        // Create skill if it doesn't exist
        const skill = await prisma.skill.upsert({
          where: { name: skillName },
          update: {},
          create: { name: skillName }
        })

        // Create the relationship
        await prisma.skillOnUser.create({
          data: {
            userId: user.id,
            skillId: skill.id
          }
        })
      }
    }

    // Handle offers
    if (offers) {
      // Delete existing offers
      await prisma.offer.deleteMany({
        where: { userId: user.id }
      })

      // Parse offers from array or comma-separated string
      const offerTags = Array.isArray(offers) ? offers : offers.split(',').map(s => s.trim()).filter(s => s.length > 0)
      
      for (const tag of offerTags) {
        await prisma.offer.create({
          data: {
            userId: user.id,
            tag: tag
          }
        })
      }
    }

    // Handle lookingFor
    if (lookingFor) {
      // Delete existing lookingFor
      await prisma.lookingFor.deleteMany({
        where: { userId: user.id }
      })

      // Parse lookingFor from array or comma-separated string
      const lookingForTags = Array.isArray(lookingFor) ? lookingFor : lookingFor.split(',').map(s => s.trim()).filter(s => s.length > 0)
      
      for (const tag of lookingForTags) {
        await prisma.lookingFor.create({
          data: {
            userId: user.id,
            tag: tag
          }
        })
      }
    }

    // Fetch the complete profile with relations
    const completeProfile = await prisma.user.findUnique({
      where: { id: user.id },
      include: {
        skills: {
          include: {
            skill: true
          }
        },
        offers: true,
        lookingFor: true,
        startups: true
      }
    })

    return NextResponse.json(completeProfile)
  } catch (error) {
    console.error('Error updating profile:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
