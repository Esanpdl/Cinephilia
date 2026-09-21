import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { motion, useReducedMotion } from 'motion/react'
import { ArrowUpRight, Menu, Search, X } from 'lucide-react'
import { useSession } from '../auth/SessionProvider'
import { Button } from './ui'

export function Layout() {
  const { user } = useSession()
  const [menu, setMenu] = useState(false)
  const location = useLocation()
  const reduced = useReducedMotion()
  useEffect(() => { setMenu(false); window.scrollTo({ top: 0, behavior: 'instant' }); document.title = 'Cinephilia — For the love of cinema' }, [location.pathname])
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setMenu(false) }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [])
  const links = [
    { to: '/', label: 'Discover' },
    { to: '/browse', label: 'Browse films' },
    { to: '/for-you', label: 'For you' },
    { to: '/collection', label: 'Your collection' },
    { to: '/students', label: 'Film Analysis' },
    ...(user?.is_staff ? [{ to: '/admin', label: 'Admin' }] : []),
  ]
  return <>
    <a href="#main" className="skip-link">Skip to content</a>
    <header className="site-header">
      <Link to="/" className="wordmark" aria-label="Cinephilia home" onClick={() => { setMenu(false); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>CINEPHILIA<span aria-hidden="true">.</span></Link>
      <nav className={'main-nav ' + (menu ? 'is-open' : '')} aria-label="Main navigation" id="main-navigation">
        {links.map(link => <NavLink key={link.to} to={link.to} end={link.to === '/'}>{({ isActive }) => <>{link.label}{isActive && <motion.span className="nav-indicator" layoutId="main-nav-indicator" transition={reduced ? { duration: 0 } : { type: 'spring', stiffness: 360, damping: 32 }} />}</>}</NavLink>)}
      </nav>
      <div className="header-actions"><Link className="icon-link desktop-search" to="/browse" aria-label="Search films"><Search size={19} /></Link>{user ? <Link className="account-link" to="/account" aria-label="Your account"><span className="avatar">{(user.profile?.display_name || user.username).slice(0, 1).toUpperCase()}</span><span className="account-label">Account</span></Link> : <Link to="/login" className="header-signin">Sign in <ArrowUpRight size={14} /></Link>}<Button className="icon-button mobile-menu" aria-label={menu ? 'Close navigation' : 'Open navigation'} aria-expanded={menu} aria-controls="main-navigation" onClick={() => setMenu(!menu)}>{menu ? <X size={22} /> : <Menu size={22} />}</Button></div>
    </header>
    <main id="main"><Outlet /></main>
    <footer className="site-footer">
      <div className="footer-top"><Link to="/" className="wordmark">CINEPHILIA<span>.</span></Link><p>For the films that stay with you.</p><Link to="/browse">Keep exploring <ArrowUpRight size={16} /></Link></div>
      <div className="footer-bottom"><span>An independent cinema discovery project.</span><span>Film data & imagery: <a href="https://www.themoviedb.org/" target="_blank" rel="noreferrer">TMDB</a>. This product uses the TMDB API but is not endorsed or certified by TMDB.</span></div>
    </footer>
  </>
}
