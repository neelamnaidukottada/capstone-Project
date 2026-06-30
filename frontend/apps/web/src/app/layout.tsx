import type { Metadata } from 'next'
import type { ReactNode } from 'react'
import { Space_Grotesk, Source_Serif_4 } from 'next/font/google'
import './globals.css'
import { Providers } from '@/components/providers'

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display',
})

const sourceSerif = Source_Serif_4({
  subsets: ['latin'],
  variable: '--font-body',
})

export const metadata: Metadata = {
  title: 'Autonomous Campaign Manager',
  description: 'AI-powered marketing campaign orchestration platform',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${spaceGrotesk.variable} ${sourceSerif.variable}`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
