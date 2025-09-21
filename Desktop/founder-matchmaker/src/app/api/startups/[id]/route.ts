import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const supabase = await createClient()
    const { data: { user }, error: authError } = await supabase.auth.getUser()

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const startup = await prisma.startup.findFirst({
      where: {
        id,
        ownerId: user.id
      }
    })

    if (!startup) {
      return NextResponse.json({ error: 'Startup not found' }, { status: 404 })
    }

    return NextResponse.json(startup)
  } catch (error) {
    console.error('Error fetching startup:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const supabase = await createClient()
    const { data: { user }, error: authError } = await supabase.auth.getUser()

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const body = await request.json()

    // Check if startup exists and belongs to user
    const existingStartup = await prisma.startup.findFirst({
      where: {
        id,
        ownerId: user.id
      }
    })

    if (!existingStartup) {
      return NextResponse.json({ error: 'Startup not found' }, { status: 404 })
    }

    const updatedStartup = await prisma.startup.update({
      where: {
        id
      },
      data: {
        name: body.name,
        oneLiner: body.oneLiner,
        stage: body.stage,
        markets: body.markets || [],
        problem: body.problem,
        solution: body.solution,
        plan: body.plan,
        logoUrl: body.logoUrl,
        imageUrls: body.imageUrls || [],
        websiteUrl: body.websiteUrl,
        demoUrl: body.demoUrl,
        deckUrl: body.deckUrl,
        teamSize: body.teamSize,
        hiringNeeds: body.hiringNeeds || [],
        keywords: body.keywords || []
      }
    })

    return NextResponse.json(updatedStartup)
  } catch (error) {
    console.error('Error updating startup:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const supabase = await createClient()
    const { data: { user }, error: authError } = await supabase.auth.getUser()

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    // Check if startup exists and belongs to user
    const existingStartup = await prisma.startup.findFirst({
      where: {
        id,
        ownerId: user.id
      }
    })

    if (!existingStartup) {
      return NextResponse.json({ error: 'Startup not found' }, { status: 404 })
    }

    await prisma.startup.delete({
      where: {
        id
      }
    })

    return NextResponse.json({ message: 'Startup deleted successfully' })
  } catch (error) {
    console.error('Error deleting startup:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
