import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import { AdminContent } from '@/components/admin/admin-content'

// Force dynamic rendering
export const dynamic = 'force-dynamic'

export default async function AdminPage() {
  const supabase = createClient()
  
  const { data: { user }, error } = await supabase.auth.getUser()
  
  if (error || !user) {
    redirect('/auth/signin')
  }

  // Check if user is admin
  // In a real app, you'd check the user's role from the database
  if (user.email !== 'admin@foundermatchmaker.com') {
    redirect('/dashboard')
  }

  return <AdminContent />
}
