'use client'

import { useState, useEffect, useRef } from 'react'
import { useParams } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Send, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { toast } from 'sonner'

interface Message {
  id: string
  body: string
  senderId: string
  createdAt: string
  readAt?: string
}

interface Match {
  id: string
  user: {
    id: string
    name: string
    imageUrl?: string
    headline: string
  }
}

export default function ChatPage() {
  const params = useParams()
  const matchId = params.matchId as string
  const [messages, setMessages] = useState<Message[]>([])
  const [match, setMatch] = useState<Match | null>(null)
  const [newMessage, setNewMessage] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSending, setIsSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const supabase = createClient()

  useEffect(() => {
    if (!matchId) return

    const fetchMatch = async () => {
      try {
        const response = await fetch(`/api/matches/${matchId}`)
        if (response.ok) {
          const matchData = await response.json()
          setMatch(matchData)
        }
      } catch (error) {
        console.error('Error fetching match:', error)
        toast.error('Failed to load chat')
      }
    }

    const fetchMessages = async () => {
      try {
        const response = await fetch(`/api/matches/${matchId}/messages`)
        if (response.ok) {
          const messagesData = await response.json()
          setMessages(messagesData)
        }
      } catch (error) {
        console.error('Error fetching messages:', error)
        toast.error('Failed to load messages')
      } finally {
        setIsLoading(false)
      }
    }

    fetchMatch()
    fetchMessages()
  }, [matchId])

  useEffect(() => {
    if (!matchId) return

    // Subscribe to realtime messages
    const channel = supabase
      .channel(`match-${matchId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'messages',
          filter: `match_id=eq.${matchId}`
        },
        (payload) => {
          const newMessage = payload.new as Message
          setMessages(prev => [...prev, newMessage])
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [matchId, supabase])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newMessage.trim() || isSending) return

    setIsSending(true)
    try {
      const response = await fetch(`/api/matches/${matchId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          body: newMessage.trim()
        })
      })

      if (response.ok) {
        setNewMessage('')
      } else {
        const error = await response.json()
        toast.error(error.error || 'Failed to send message')
      }
    } catch (error) {
      console.error('Error sending message:', error)
      toast.error('Failed to send message')
    } finally {
      setIsSending(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-2 text-gray-500">Loading chat...</p>
        </div>
      </div>
    )
  }

  if (!match) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-900">Chat not found</h2>
          <p className="text-gray-500 mt-2">This chat doesn't exist or you don't have access to it.</p>
          <Button asChild className="mt-4">
            <Link href="/matches">Back to Matches</Link>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <Button variant="ghost" size="sm" asChild className="mr-4">
              <Link href="/matches">
                <ArrowLeft className="h-4 w-4" />
              </Link>
            </Button>
            <div className="flex items-center space-x-3">
              <Avatar>
                <AvatarImage src={match.user.imageUrl} />
                <AvatarFallback>{match.user.name.charAt(0)}</AvatarFallback>
              </Avatar>
              <div>
                <h1 className="font-semibold">{match.user.name}</h1>
                <p className="text-sm text-gray-500">{match.user.headline}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Card className="h-[600px] flex flex-col">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Messages</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto space-y-4">
            {messages.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                <p>No messages yet. Start the conversation!</p>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.senderId === match.user.id ? 'justify-start' : 'justify-end'}`}
                >
                  <div
                    className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                      message.senderId === match.user.id
                        ? 'bg-gray-100 text-gray-900'
                        : 'bg-blue-500 text-white'
                    }`}
                  >
                    <p className="text-sm">{message.body}</p>
                    <p className={`text-xs mt-1 ${
                      message.senderId === match.user.id ? 'text-gray-500' : 'text-blue-100'
                    }`}>
                      {new Date(message.createdAt).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </CardContent>

          {/* Message Input */}
          <div className="p-4 border-t">
            <form onSubmit={handleSendMessage} className="flex space-x-2">
              <Input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                placeholder="Type your message..."
                disabled={isSending}
                className="flex-1"
              />
              <Button type="submit" disabled={!newMessage.trim() || isSending}>
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </Card>
      </div>
    </div>
  )
}
