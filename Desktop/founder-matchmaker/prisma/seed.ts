import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

const skills = [
  'React', 'Vue.js', 'Angular', 'Node.js', 'Python', 'Java', 'Go', 'Rust',
  'TypeScript', 'JavaScript', 'PostgreSQL', 'MongoDB', 'Redis', 'AWS', 'Docker',
  'Kubernetes', 'GraphQL', 'REST API', 'Machine Learning', 'AI', 'Data Science',
  'Product Management', 'UI/UX Design', 'Marketing', 'Sales', 'Operations',
  'Finance', 'Legal', 'DevOps', 'Security', 'Mobile Development', 'Web3',
  'Blockchain', 'Fintech', 'Healthtech', 'Edtech', 'E-commerce', 'SaaS'
]

const offers = [
  'Technical Co-founder', 'Product Management', 'UI/UX Design', 'Marketing',
  'Sales', 'Operations', 'Finance', 'Legal', 'Advisor', 'Fractional CTO',
  'Backend Development', 'Frontend Development', 'Mobile Development',
  'Data Engineering', 'DevOps', 'Security', 'AI/ML', 'Blockchain',
  'Growth Marketing', 'Content Marketing', 'Business Development'
]

const lookingFor = [
  'Technical Co-founder', 'Product Management', 'UI/UX Design', 'Marketing',
  'Sales', 'Operations', 'Finance', 'Legal', 'Advisor', 'Fractional CTO',
  'Backend Development', 'Frontend Development', 'Mobile Development',
  'Data Engineering', 'DevOps', 'Security', 'AI/ML', 'Blockchain',
  'Growth Marketing', 'Content Marketing', 'Business Development'
]

const mockUsers = [
  {
    id: 'user-1',
    email: 'sarah.chen@example.com',
    name: 'Sarah Chen',
    headline: 'Full-stack developer with 5+ years in fintech',
    bio: 'Passionate about building scalable fintech solutions. Previously at Stripe and Coinbase. Looking to build the next generation of payment infrastructure that makes financial services accessible to everyone.',
    location: 'San Francisco, CA',
    timezone: 'UTC-08:00',
    availability: 80,
    equityPref: 'both',
    remotePref: 'hybrid',
    languages: ['English', 'Mandarin'],
    imageUrl: 'https://images.unsplash.com/photo-1494790108755-2616b612b786?w=150&h=150&fit=crop&crop=face',
    whatsapp: '+14155551234',
    linkedin: 'https://linkedin.com/in/sarahchen',
    github: 'https://github.com/sarahchen',
    skills: ['React', 'Node.js', 'TypeScript', 'PostgreSQL', 'AWS'],
    offers: ['Backend Development', 'Technical Leadership'],
    lookingFor: ['Product Management', 'UI/UX Design', 'Marketing']
  },
  {
    id: 'user-2',
    email: 'marcus.johnson@example.com',
    name: 'Marcus Johnson',
    headline: 'Product strategist and growth expert',
    bio: 'Former PM at Google and Uber. Expert in product-market fit, user acquisition, and scaling products from 0 to 1M users. Passionate about AI and machine learning applications in consumer products.',
    location: 'New York, NY',
    timezone: 'UTC-05:00',
    availability: 60,
    equityPref: 'equity',
    remotePref: 'remote',
    languages: ['English'],
    imageUrl: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150&h=150&fit=crop&crop=face',
    whatsapp: '+12125551234',
    linkedin: 'https://linkedin.com/in/marcusjohnson',
    github: 'https://github.com/marcusjohnson',
    skills: ['Product Management', 'Growth Marketing', 'Data Science', 'AI'],
    offers: ['Product Management', 'Growth Strategy'],
    lookingFor: ['Technical Co-founder', 'Backend Development']
  },
  {
    id: 'user-3',
    email: 'elena.rodriguez@example.com',
    name: 'Elena Rodriguez',
    headline: 'UI/UX Designer with startup experience',
    bio: 'Designer with 4+ years creating beautiful, user-centered products. Led design at 2 successful exits. Specialized in mobile-first design and design systems that scale.',
    location: 'Austin, TX',
    timezone: 'UTC-06:00',
    availability: 90,
    equityPref: 'both',
    remotePref: 'hybrid',
    languages: ['English', 'Spanish'],
    imageUrl: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&h=150&fit=crop&crop=face',
    whatsapp: '+15125551234',
    linkedin: 'https://linkedin.com/in/elenarodriguez',
    github: 'https://github.com/elenarodriguez',
    skills: ['UI/UX Design', 'Product Design', 'Figma', 'User Research'],
    offers: ['UI/UX Design', 'User Research'],
    lookingFor: ['Technical Co-founder', 'Product Management']
  },
  {
    id: 'user-4',
    email: 'alex.kim@example.com',
    name: 'Alex Kim',
    headline: 'AI/ML Engineer with startup experience',
    bio: 'AI researcher turned engineer. Built ML systems at scale for recommendation engines and computer vision. Passionate about applying AI to solve real-world problems in healthcare and education.',
    location: 'Seattle, WA',
    timezone: 'UTC-08:00',
    availability: 70,
    equityPref: 'equity',
    remotePref: 'remote',
    languages: ['English', 'Korean'],
    imageUrl: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop&crop=face',
    whatsapp: '+12065551234',
    linkedin: 'https://linkedin.com/in/alexkim',
    github: 'https://github.com/alexkim',
    skills: ['Machine Learning', 'Python', 'TensorFlow', 'PyTorch', 'Computer Vision'],
    offers: ['AI', 'Technical Co-founder'],
    lookingFor: ['Product Management', 'UI/UX Design', 'Marketing']
  },
  {
    id: 'user-5',
    email: 'jessica.wang@example.com',
    name: 'Jessica Wang',
    headline: 'Marketing expert and growth hacker',
    bio: 'Growth marketer with 6+ years scaling B2B SaaS companies. Expert in content marketing, SEO, and paid acquisition. Led marketing at 3 successful exits.',
    location: 'Los Angeles, CA',
    timezone: 'UTC-08:00',
    availability: 85,
    equityPref: 'both',
    remotePref: 'hybrid',
    languages: ['English', 'Mandarin'],
    imageUrl: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=150&h=150&fit=crop&crop=face',
    whatsapp: '+13105551234',
    linkedin: 'https://linkedin.com/in/jessicawang',
    github: 'https://github.com/jessicawang',
    skills: ['Growth Marketing', 'Content Marketing', 'SEO', 'Paid Acquisition'],
    offers: ['Marketing', 'Growth Strategy'],
    lookingFor: ['Technical Co-founder', 'Product Management']
  },
  {
    id: 'user-6',
    email: 'david.thompson@example.com',
    name: 'David Thompson',
    headline: 'Serial entrepreneur and business strategist',
    bio: 'Built and sold 2 companies in the B2B SaaS space. Expert in fundraising, business development, and scaling operations. Currently looking for technical co-founders for my next venture in the climate tech space.',
    location: 'Denver, CO',
    timezone: 'UTC-07:00',
    availability: 95,
    equityPref: 'equity',
    remotePref: 'hybrid',
    languages: ['English'],
    imageUrl: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&h=150&fit=crop&crop=face',
    whatsapp: '+13035551234',
    linkedin: 'https://linkedin.com/in/davidthompson',
    github: 'https://github.com/davidthompson',
    skills: ['Business Development', 'Operations', 'Finance', 'Legal'],
    offers: ['Business Development', 'Operations', 'Advisor'],
    lookingFor: ['Technical Co-founder', 'AI', 'Backend Development']
  },
  {
    id: 'user-7',
    email: 'priya.patel@example.com',
    name: 'Priya Patel',
    headline: 'Mobile developer and startup founder',
    bio: 'iOS and Android developer with 6+ years experience. Founded a successful mobile app that reached 1M+ downloads. Passionate about creating mobile experiences that solve real problems.',
    location: 'Toronto, ON',
    timezone: 'UTC-05:00',
    availability: 75,
    equityPref: 'both',
    remotePref: 'remote',
    languages: ['English', 'Hindi', 'Gujarati'],
    imageUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&h=150&fit=crop&crop=face',
    whatsapp: '+14165551234',
    linkedin: 'https://linkedin.com/in/priyapatel',
    github: 'https://github.com/priyapatel',
    skills: ['Mobile Development', 'React Native', 'Swift', 'Kotlin', 'Firebase'],
    offers: ['Mobile Development', 'Technical Co-founder'],
    lookingFor: ['Product Management', 'Marketing', 'UI/UX Design']
  },
  {
    id: 'user-8',
    email: 'james.wilson@example.com',
    name: 'James Wilson',
    headline: 'DevOps engineer and cloud architect',
    bio: 'Infrastructure expert with 8+ years building scalable systems. Led DevOps at multiple unicorn startups. Specialized in AWS, Kubernetes, and building systems that scale to millions of users.',
    location: 'London, UK',
    timezone: 'UTC+00:00',
    availability: 65,
    equityPref: 'equity',
    remotePref: 'remote',
    languages: ['English'],
    imageUrl: 'https://images.unsplash.com/photo-1560250097-0b93528c311a?w=150&h=150&fit=crop&crop=face',
    whatsapp: '+447700900123',
    linkedin: 'https://linkedin.com/in/jameswilson',
    github: 'https://github.com/jameswilson',
    skills: ['DevOps', 'AWS', 'Kubernetes', 'Docker', 'Security'],
    offers: ['DevOps', 'Technical Leadership', 'Advisor'],
    lookingFor: ['Product Management', 'Marketing', 'Business Development']
  }
]

const mockStartups = [
  {
    id: 'startup-1',
    ownerId: 'user-1',
    name: 'PayFlow',
    oneLiner: 'Next-generation payment infrastructure for small businesses',
    problem: 'Small businesses struggle with high payment processing fees and slow settlements',
    solution: 'PayFlow simplifies payment processing for small businesses with instant settlements, lower fees, and powerful analytics. Our API-first approach makes integration seamless.',
    stage: 'mvp',
    markets: ['Fintech', 'B2B', 'Payments'],
    teamSize: 3,
    logoUrl: 'https://images.unsplash.com/photo-1611224923853-80b023f02d71?w=100&h=100&fit=crop',
    websiteUrl: 'https://payflow.dev',
    imageUrls: ['https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=400&h=300&fit=crop'],
    hiringNeeds: ['Backend Developer', 'Sales'],
    keywords: ['fintech', 'payments', 'small business', 'API']
  },
  {
    id: 'startup-2',
    ownerId: 'user-2',
    name: 'MindfulAI',
    oneLiner: 'AI-powered mental health companion for professionals',
    problem: 'Professionals struggle with stress and mental health but lack accessible, personalized support',
    solution: 'MindfulAI uses advanced AI to provide personalized mental health support, stress management, and productivity coaching for busy professionals.',
    stage: 'idea',
    markets: ['Healthcare', 'AI', 'B2C'],
    teamSize: 2,
    logoUrl: 'https://images.unsplash.com/photo-1677442136019-21780ecad995?w=100&h=100&fit=crop',
    websiteUrl: 'https://mindfulai.app',
    imageUrls: ['https://images.unsplash.com/photo-1559757148-5c350d0d3c56?w=400&h=300&fit=crop'],
    hiringNeeds: ['AI Engineer', 'UX Designer'],
    keywords: ['AI', 'mental health', 'wellness', 'productivity']
  },
  {
    id: 'startup-3',
    ownerId: 'user-3',
    name: 'DesignSync',
    oneLiner: 'Collaborative design platform for remote teams',
    problem: 'Design teams struggle with collaboration, feedback, and version control in remote work',
    solution: 'DesignSync enables design teams to collaborate seamlessly with real-time feedback, version control, and stakeholder approval workflows.',
    stage: 'prototype',
    markets: ['Design Tools', 'B2B', 'SaaS'],
    teamSize: 4,
    logoUrl: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=100&h=100&fit=crop',
    websiteUrl: 'https://designsync.io',
    imageUrls: ['https://images.unsplash.com/photo-1558655146-9f40138edfeb?w=400&h=300&fit=crop'],
    hiringNeeds: ['Frontend Developer', 'Product Manager'],
    keywords: ['design', 'collaboration', 'remote work', 'feedback']
  },
  {
    id: 'startup-4',
    ownerId: 'user-6',
    name: 'GreenTech Solutions',
    oneLiner: 'Carbon tracking and reduction platform for enterprises',
    problem: 'Enterprises lack comprehensive tools to track and reduce their carbon footprint effectively',
    solution: 'Help enterprises track, analyze, and reduce their carbon footprint with our comprehensive sustainability platform and AI-powered recommendations.',
    stage: 'mvp',
    markets: ['Climate Tech', 'B2B', 'Enterprise'],
    teamSize: 5,
    logoUrl: 'https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?w=100&h=100&fit=crop',
    websiteUrl: 'https://greentech-solutions.com',
    imageUrls: ['https://images.unsplash.com/photo-1497435334941-8c899ee9e8e9?w=400&h=300&fit=crop'],
    hiringNeeds: ['Data Scientist', 'Enterprise Sales'],
    keywords: ['climate tech', 'sustainability', 'carbon tracking', 'enterprise']
  },
  {
    id: 'startup-5',
    ownerId: 'user-7',
    name: 'FitBuddy',
    oneLiner: 'Social fitness app connecting workout partners',
    problem: 'People struggle to stay motivated and find workout partners with similar fitness goals',
    solution: 'FitBuddy connects people with similar fitness goals and schedules, making it easy to find workout partners and stay motivated.',
    stage: 'revenue',
    markets: ['Health & Fitness', 'Social', 'Mobile'],
    teamSize: 6,
    logoUrl: 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=100&h=100&fit=crop',
    websiteUrl: 'https://fitbuddy.app',
    imageUrls: ['https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=400&h=300&fit=crop'],
    hiringNeeds: ['Mobile Developer', 'Growth Marketer'],
    keywords: ['fitness', 'social', 'mobile app', 'health']
  }
]

async function main() {
  console.log('🌱 Starting seed...')

  // Create skills
  console.log('Creating skills...')
  for (const skillName of skills) {
    await prisma.skill.upsert({
      where: { name: skillName },
      update: {},
      create: { name: skillName }
    })
  }

  // Create users (only if they don't exist)
  console.log('Creating users...')
  for (const userData of mockUsers) {
    const { skills: userSkills, offers: userOffers, lookingFor: userLookingFor, ...user } = userData

    // Check if user already exists
    const existingUser = await prisma.user.findUnique({
      where: { id: user.id }
    })

    // Only create user and their data if they don't exist
    if (!existingUser) {
      await prisma.user.create({
        data: user
      })

      // Add skills
      for (const skillName of userSkills) {
        const skill = await prisma.skill.findUnique({
          where: { name: skillName }
        })

        if (skill) {
          await prisma.skillOnUser.create({
            data: {
              userId: user.id,
              skillId: skill.id
            }
          })
        }
      }

      // Add offers
      for (const offer of userOffers) {
        await prisma.offer.create({
          data: {
            userId: user.id,
            tag: offer
          }
        })
      }

      // Add looking for
      for (const lookingForItem of userLookingFor) {
        await prisma.lookingFor.create({
          data: {
            userId: user.id,
            tag: lookingForItem
          }
        })
      }
    }
  }

  // Create startups
  console.log('Creating startups...')
  for (const startup of mockStartups) {
    await prisma.startup.upsert({
      where: { id: startup.id },
      update: {},
      create: startup
    })
  }

  // Create some matches
  console.log('Creating matches...')
  await prisma.match.upsert({
    where: {
      userAId_userBId: {
        userAId: 'user-1',
        userBId: 'user-2'
      }
    },
    update: {},
    create: {
      userAId: 'user-1',
      userBId: 'user-2'
    }
  })

  await prisma.match.upsert({
    where: {
      userAId_userBId: {
        userAId: 'user-3',
        userBId: 'user-4'
      }
    },
    update: {},
    create: {
      userAId: 'user-3',
      userBId: 'user-4'
    }
  })

  await prisma.match.upsert({
    where: {
      userAId_userBId: {
        userAId: 'user-5',
        userBId: 'user-6'
      }
    },
    update: {},
    create: {
      userAId: 'user-5',
      userBId: 'user-6'
    }
  })

  // Create some sample messages
  console.log('Creating sample messages...')
  const match1 = await prisma.match.findFirst({
    where: {
      OR: [
        { userAId: 'user-1', userBId: 'user-2' },
        { userAId: 'user-2', userBId: 'user-1' }
      ]
    }
  })

  const match2 = await prisma.match.findFirst({
    where: {
      OR: [
        { userAId: 'user-3', userBId: 'user-4' },
        { userAId: 'user-4', userBId: 'user-3' }
      ]
    }
  })

  const match3 = await prisma.match.findFirst({
    where: {
      OR: [
        { userAId: 'user-5', userBId: 'user-6' },
        { userAId: 'user-6', userBId: 'user-5' }
      ]
    }
  })

  if (match1) {
    // Clear existing messages first
    await prisma.message.deleteMany({
      where: { matchId: match1.id }
    })
    
    await prisma.message.createMany({
      data: [
        {
          matchId: match1.id,
          senderId: 'user-1',
          body: 'Hey Marcus! I saw your profile and I think we could build something amazing together.'
        },
        {
          matchId: match1.id,
          senderId: 'user-2',
          body: 'Hi Sarah! I\'m excited to learn more about your fintech experience. What kind of product are you thinking about?'
        },
        {
          matchId: match1.id,
          senderId: 'user-1',
          body: 'I\'m working on a new payment infrastructure that could revolutionize how small businesses handle transactions. Would love to discuss!'
        },
        {
          matchId: match1.id,
          senderId: 'user-2',
          body: 'That sounds fascinating! I have experience scaling payment systems at Uber. When would be a good time to chat?'
        }
      ]
    })
  }

  if (match2) {
    // Clear existing messages first
    await prisma.message.deleteMany({
      where: { matchId: match2.id }
    })
    
    await prisma.message.createMany({
      data: [
        {
          matchId: match2.id,
          senderId: 'user-3',
          body: 'Hi Alex! Your AI background is impressive. I\'m working on a design platform that could benefit from ML.'
        },
        {
          matchId: match2.id,
          senderId: 'user-4',
          body: 'Thanks Elena! I\'d love to hear more about your design platform. AI could definitely help with automated design suggestions.'
        },
        {
          matchId: match2.id,
          senderId: 'user-3',
          body: 'Exactly what I was thinking! Let\'s schedule a call to discuss the possibilities.'
        }
      ]
    })
  }

  if (match3) {
    // Clear existing messages first
    await prisma.message.deleteMany({
      where: { matchId: match3.id }
    })
    
    await prisma.message.createMany({
      data: [
        {
          matchId: match3.id,
          senderId: 'user-5',
          body: 'Hi David! I saw your climate tech startup idea. My marketing expertise could help with user acquisition.'
        },
        {
          matchId: match3.id,
          senderId: 'user-6',
          body: 'Jessica! Perfect timing. I need someone who understands B2B marketing for enterprise clients. Let\'s connect!'
        }
      ]
    })
  }

  console.log('✅ Seed completed!')
}

main()
  .catch((e) => {
    console.error('❌ Seed failed:', e)
    process.exit(1)
  })
  .finally(async () => {
    await prisma.$disconnect()
  })
