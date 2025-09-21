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

    const matches = await prisma.match.findMany({
      where: {
        OR: [
          { userAId: user.id },
          { userBId: user.id }
        ],
        active: true
      },
      include: {
        userA: {
          select: {
            id: true,
            name: true,
            imageUrl: true,
            headline: true,
            location: true,
            whatsapp: true
          }
        },
        userB: {
          select: {
            id: true,
            name: true,
            imageUrl: true,
            headline: true,
            location: true,
            whatsapp: true
          }
        }
      },
      orderBy: {
        createdAt: 'desc'
      }
    })

    // Get the original like messages for each match
    const matchesWithMessages = await Promise.all(
      matches.map(async (match) => {
        const otherUser = match.userAId === user.id ? match.userB : match.userA
        
        // Get the original like message from the other user
        const originalLike = await prisma.like.findUnique({
          where: {
            fromId_toId: {
              fromId: otherUser.id,
              toId: user.id
            }
          }
        })

        return {
          id: match.id,
          user: otherUser,
          originalMessage: originalLike?.message || null,
          matchedAt: match.createdAt
        }
      })
    )

    const formattedMatches = matchesWithMessages

    return NextResponse.json(formattedMatches)
  } catch (error) {
    console.error('Error fetching matches:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
