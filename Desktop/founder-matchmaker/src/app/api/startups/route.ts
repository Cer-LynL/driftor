import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'
import { startupSchema } from '@/lib/validations/profile'

export async function GET(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { data: { user }, error } = await supabase.auth.getUser()

    if (error || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const startups = await prisma.startup.findMany({
      where: {
        ownerId: user.id
      },
      orderBy: {
        createdAt: 'desc'
      }
    })

    return NextResponse.json(startups)
  } catch (error) {
    console.error('Error fetching startups:', error)
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
    const validatedData = startupSchema.parse(body)

    const startup = await prisma.startup.create({
      data: {
        ...validatedData,
        ownerId: user.id
      }
    })

    return NextResponse.json(startup)
  } catch (error) {
    console.error('Error creating startup:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
