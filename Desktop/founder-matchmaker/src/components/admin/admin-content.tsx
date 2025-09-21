'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Users, MessageSquare, Flag, BarChart3 } from 'lucide-react'

interface User {
  id: string
  name: string
  email: string
  role: string
  createdAt: string
  reports: number
}

interface Report {
  id: string
  reporter: {
    name: string
    email: string
  }
  targetUser: {
    name: string
    email: string
  }
  reason: string
  createdAt: string
}

interface Stats {
  totalUsers: number
  totalMatches: number
  totalMessages: number
  totalReports: number
}

export function AdminContent() {
  const [users, setUsers] = useState<User[]>([])
  const [reports, setReports] = useState<Report[]>([])
  const [stats, setStats] = useState<Stats>({
    totalUsers: 0,
    totalMatches: 0,
    totalMessages: 0,
    totalReports: 0
  })
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      // In a real app, these would be API calls
      // For now, we'll use mock data
      setUsers([
        {
          id: '1',
          name: 'John Doe',
          email: 'john@example.com',
          role: 'user',
          createdAt: '2024-01-15',
          reports: 0
        },
        {
          id: '2',
          name: 'Jane Smith',
          email: 'jane@example.com',
          role: 'user',
          createdAt: '2024-01-16',
          reports: 1
        },
        {
          id: '3',
          name: 'Bob Johnson',
          email: 'bob@example.com',
          role: 'user',
          createdAt: '2024-01-17',
          reports: 0
        }
      ])

      setReports([
        {
          id: '1',
          reporter: {
            name: 'Alice Wilson',
            email: 'alice@example.com'
          },
          targetUser: {
            name: 'Jane Smith',
            email: 'jane@example.com'
          },
          reason: 'Inappropriate behavior in chat',
          createdAt: '2024-01-18'
        }
      ])

      setStats({
        totalUsers: 150,
        totalMatches: 45,
        totalMessages: 1200,
        totalReports: 3
      })
    } catch (error) {
      console.error('Error fetching admin data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleUserAction = async (userId: string, action: 'suspend' | 'delete') => {
    // In a real app, this would make an API call
    console.log(`${action} user ${userId}`)
  }

  const handleReportAction = async (reportId: string, action: 'dismiss' | 'investigate') => {
    // In a real app, this would make an API call
    console.log(`${action} report ${reportId}`)
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-2 text-gray-500">Loading admin panel...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Admin Panel</h1>
          <p className="text-gray-500 mt-2">Manage users, reports, and platform statistics</p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center">
                <Users className="h-8 w-8 text-blue-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Total Users</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.totalUsers}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center">
                <MessageSquare className="h-8 w-8 text-green-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Total Matches</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.totalMatches}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center">
                <BarChart3 className="h-8 w-8 text-purple-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Messages Sent</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.totalMessages}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center">
                <Flag className="h-8 w-8 text-red-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Reports</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.totalReports}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <Tabs defaultValue="users" className="space-y-6">
          <TabsList>
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="reports">Reports</TabsTrigger>
            <TabsTrigger value="analytics">Analytics</TabsTrigger>
          </TabsList>

          <TabsContent value="users" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>User Management</CardTitle>
                <CardDescription>
                  Manage user accounts and permissions
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {users.map((user) => (
                    <div key={user.id} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3">
                          <div>
                            <h3 className="font-semibold">{user.name}</h3>
                            <p className="text-sm text-gray-500">{user.email}</p>
                          </div>
                          <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>
                            {user.role}
                          </Badge>
                          {user.reports > 0 && (
                            <Badge variant="destructive">
                              {user.reports} reports
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-gray-400 mt-1">
                          Joined: {new Date(user.createdAt).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="flex space-x-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleUserAction(user.id, 'suspend')}
                        >
                          Suspend
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleUserAction(user.id, 'delete')}
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="reports" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>User Reports</CardTitle>
                <CardDescription>
                  Review and take action on user reports
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {reports.map((report) => (
                    <div key={report.id} className="p-4 border rounded-lg">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-2">
                            <span className="text-sm font-medium">Reported by:</span>
                            <span className="text-sm">{report.reporter.name}</span>
                            <span className="text-sm text-gray-500">({report.reporter.email})</span>
                          </div>
                          <div className="flex items-center space-x-2 mb-2">
                            <span className="text-sm font-medium">Reported user:</span>
                            <span className="text-sm">{report.targetUser.name}</span>
                            <span className="text-sm text-gray-500">({report.targetUser.email})</span>
                          </div>
                          <p className="text-sm text-gray-600 mb-2">
                            <strong>Reason:</strong> {report.reason}
                          </p>
                          <p className="text-xs text-gray-400">
                            {new Date(report.createdAt).toLocaleString()}
                          </p>
                        </div>
                        <div className="flex space-x-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleReportAction(report.id, 'dismiss')}
                          >
                            Dismiss
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleReportAction(report.id, 'investigate')}
                          >
                            Investigate
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="analytics" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Platform Analytics</CardTitle>
                <CardDescription>
                  Key metrics and insights
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-8">
                  <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-500">Analytics dashboard coming soon...</p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
