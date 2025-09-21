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

    // Get all likes received by the current user
    const receivedLikes = await prisma.like.findMany({
      where: {
        toId: user.id
      },
      include: {
        from: {
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

    // Check which ones are already matched (mutual likes)
    const matches = await prisma.match.findMany({
      where: {
        OR: [
          { userAId: user.id },
          { userBId: user.id }
        ]
      }
    })

    const matchedUserIds = new Set(
      matches.map(match => 
        match.userAId === user.id ? match.userBId : match.userAId
      )
    )

    // Filter out already matched invitations
    const invitations = receivedLikes.filter(like => 
      !matchedUserIds.has(like.fromId)
    )

    return NextResponse.json(invitations)
  } catch (error) {
    console.error('Error fetching invitations:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
