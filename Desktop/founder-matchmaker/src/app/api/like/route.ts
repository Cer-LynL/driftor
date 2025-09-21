import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'
import { z } from 'zod'

const likeSchema = z.object({
  toUserId: z.string().uuid(),
  message: z.string().optional()
})

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { data: { user }, error } = await supabase.auth.getUser()

    if (error || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await request.json()
    const { toUserId, message } = likeSchema.parse(body)

    if (user.id === toUserId) {
      return NextResponse.json({ error: 'Cannot like yourself' }, { status: 400 })
    }

    // Check if user exists
    const targetUser = await prisma.user.findUnique({
      where: { id: toUserId }
    })

    if (!targetUser) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 })
    }

    // Check if already liked
    const existingLike = await prisma.like.findUnique({
      where: {
        fromId_toId: {
          fromId: user.id,
          toId: toUserId
        }
      }
    })

    if (existingLike) {
      return NextResponse.json({ error: 'Already liked this user' }, { status: 400 })
    }

    // Create the like
    const like = await prisma.like.create({
      data: {
        fromId: user.id,
        toId: toUserId,
        message: message
      }
    })

    // Check if it's a mutual like (match)
    const mutualLike = await prisma.like.findUnique({
      where: {
        fromId_toId: {
          fromId: toUserId,
          toId: user.id
        }
      }
    })

    if (mutualLike) {
      // Create a match
      const match = await prisma.match.create({
        data: {
          userAId: user.id,
          userBId: toUserId
        }
      })

      return NextResponse.json({ 
        like, 
        match,
        isMatch: true,
        message: 'It\'s a match! 🎉'
      })
    }

    return NextResponse.json({ 
      like, 
      isMatch: false,
      message: 'Like sent! You\'ll be notified if they like you back.'
    })
  } catch (error) {
    console.error('Error creating like:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
