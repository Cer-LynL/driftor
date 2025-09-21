'use client'

import { BeamsBackground } from '@/components/ui/beams-background'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

export default function LandingPage() {
  const router = useRouter()

  return (
    <BeamsBackground>
      <div className="relative z-10 flex h-screen w-full items-center justify-center">
        <div className="flex flex-col items-center justify-center gap-6 px-4 text-center">
          <h1 className="text-6xl md:text-7xl lg:text-8xl font-semibold text-white tracking-tighter">
            Founder
            <br />
            Matchmaker
          </h1>
          <p className="text-lg md:text-2xl lg:text-3xl text-white/70 tracking-tighter max-w-2xl">
            Connect with your perfect co-founder. Find complementary skills, shared vision, and build the next big thing together.
          </p>
          <div className="mt-8 flex gap-4">
            <Button 
              size="lg" 
              className="bg-white text-black hover:bg-white/90 rounded-full cursor-pointer focus:outline-none"
              onClick={() => {
                console.log('Get Started clicked!');
                router.push('/auth/signup');
              }}
            >
              Get Started
            </Button>
            <Button 
              size="lg" 
              className="bg-black text-white hover:bg-black/80 border border-white/20 rounded-full cursor-pointer"
              onClick={() => {
                console.log('Sign In clicked!');
                router.push('/auth/signin');
              }}
            >
              Sign In
            </Button>
          </div>
        </div>
      </div>
    </BeamsBackground>
  )
}
