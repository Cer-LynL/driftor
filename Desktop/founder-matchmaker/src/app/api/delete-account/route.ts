import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'

export async function DELETE(request: NextRequest) {
  try {
    const supabase = await createClient()
    const { data: { user }, error } = await supabase.auth.getUser()

    if (error || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    console.log(`🗑️ Starting account deletion for user: ${user.email}`)

    // Delete all user data from database in correct order (respecting foreign key constraints)
    
    // 1. Delete messages
    await prisma.message.deleteMany({
      where: { senderId: user.id }
    })
    console.log('✅ Deleted user messages')

    // 2. Delete matches where user is involved
    await prisma.match.deleteMany({
      where: {
        OR: [
          { userAId: user.id },
          { userBId: user.id }
        ]
      }
    })
    console.log('✅ Deleted user matches')

    // 3. Delete likes sent and received
    await prisma.like.deleteMany({
      where: {
        OR: [
          { fromId: user.id },
          { toId: user.id }
        ]
      }
    })
    console.log('✅ Deleted user likes')

    // 4. Delete reports
    await prisma.report.deleteMany({
      where: { reporterId: user.id }
    })
    console.log('✅ Deleted user reports')

    // 5. Delete startups owned by user
    await prisma.startup.deleteMany({
      where: { ownerId: user.id }
    })
    console.log('✅ Deleted user startups')

    // 6. Delete user skills
    await prisma.skillOnUser.deleteMany({
      where: { userId: user.id }
    })
    console.log('✅ Deleted user skills')

    // 7. Delete offers
    await prisma.offer.deleteMany({
      where: { userId: user.id }
    })
    console.log('✅ Deleted user offers')

    // 8. Delete looking for
    await prisma.lookingFor.deleteMany({
      where: { userId: user.id }
    })
    console.log('✅ Deleted user looking for')

    // 9. Finally delete the user record
    await prisma.user.delete({
      where: { id: user.id }
    })
    console.log('✅ Deleted user profile')

    // 10. Delete from Supabase Auth (this will also log them out)
    const { error: authError } = await supabase.auth.admin.deleteUser(user.id)
    
    if (authError) {
      console.error('❌ Error deleting from Supabase Auth:', authError.message)
      // Continue anyway since database cleanup was successful
    } else {
      console.log('✅ Deleted user from Supabase Auth')
    }

    console.log(`🎯 Account deletion completed for: ${user.email}`)

    return NextResponse.json({ 
      message: 'Account deleted successfully',
      deleted: true
    })

  } catch (error) {
    console.error('❌ Error deleting account:', error)
    return NextResponse.json({ 
      error: 'Failed to delete account',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 })
  }
}
