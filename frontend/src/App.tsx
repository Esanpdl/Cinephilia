import { lazy, Suspense } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { MotionConfig } from 'motion/react'
import { Layout } from './components/Layout'
import { ProtectedPage } from './components/ProtectedPage'
import { EmptyState } from './components/ui'
const Home = lazy(() => import('./pages/Home'))
const Browse = lazy(() => import('./pages/Browse'))
const FilmDetail = lazy(() => import('./pages/FilmDetail'))
const Auth = lazy(() => import('./pages/Auth'))
const PasswordRecovery = lazy(() => import('./pages/PasswordRecovery'))
const ForYou = lazy(() => import('./pages/ForYou'))
const Collection = lazy(() => import('./pages/Collection'))
const Account = lazy(() => import('./pages/Account'))
const PublicProfile = lazy(() => import('./pages/PublicProfile'))
const Preferences = lazy(() => import('./pages/Preferences'))
const Students = lazy(() => import('./pages/Students'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))

export default function App() {
  return <MotionConfig reducedMotion="user"><BrowserRouter><Suspense fallback={<div className="route-loading" role="status">Bringing the picture into focus…</div>}><Routes><Route element={<Layout />}>
    <Route index element={<Home />} />
    <Route path="browse" element={<Browse />} />
    <Route path="films/:id" element={<FilmDetail />} />
    <Route path="people/:id" element={<PublicProfile />} />
    <Route path="students/*" element={<Students />} />
    <Route path="login" element={<Auth key="login" />} />
    <Route path="register" element={<Auth key="register" register />} />
    <Route path="reset-password" element={<PasswordRecovery />} />
    <Route path="for-you" element={<ProtectedPage><ForYou /></ProtectedPage>} />
    <Route path="collection" element={<ProtectedPage><Collection /></ProtectedPage>} />
    <Route path="account" element={<ProtectedPage><Account /></ProtectedPage>} />
    <Route path="welcome" element={<ProtectedPage><Preferences onboarding /></ProtectedPage>} />
    <Route path="preferences" element={<ProtectedPage><Preferences /></ProtectedPage>} />
    <Route path="admin" element={<ProtectedPage><AdminDashboard /></ProtectedPage>} />
    <Route path="*" element={<EmptyState title="A scene we couldn't find."><p>This page isn't part of the picture.</p><Link to="/" className="button button-outline">Back to the beginning</Link></EmptyState>} />
  </Route></Routes></Suspense></BrowserRouter></MotionConfig>
}
