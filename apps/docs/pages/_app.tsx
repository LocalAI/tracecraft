import type { AppProps } from 'next/app'
import { useRouter } from 'next/router'
import { DocsChat } from '@/components'
import '../styles/globals.css'

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter()

  // Don't show floating chat on the full chat page
  const showFloatingChat = !router.pathname.startsWith('/playground/chat')

  return (
    <>
      <Component {...pageProps} />
      {showFloatingChat && <DocsChat />}
    </>
  )
}
