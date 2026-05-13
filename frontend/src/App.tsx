import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AuthProvider } from './context/AuthContext';
import { HomePage } from './routes/HomePage';
import { PortalsPage } from './routes/PortalsPage';
import { PortalDetailPage } from './routes/PortalDetailPage';
import { LoginPage } from './routes/LoginPage';
import { SignupPage } from './routes/SignupPage';
import { FavoritesPage } from './routes/FavoritesPage';
import { StoriesPage } from './routes/StoriesPage';
import { StoryDetailPage } from './routes/StoryDetailPage';
import { AlertsPage } from './routes/AlertsPage';
import { ArticleDetailPage } from './routes/ArticleDetailPage';
import { CategoriesPage } from './routes/CategoriesPage';
import { NoticiasPage } from './routes/NoticiasPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/noticias" element={<NoticiasPage />} />
            <Route path="/portales" element={<PortalsPage />} />
            <Route path="/portales/:slug" element={<PortalDetailPage />} />
            <Route path="/articulos/:id" element={<ArticleDetailPage />} />
            <Route path="/historias" element={<StoriesPage />} />
            <Route path="/historias/:id" element={<StoryDetailPage />} />
            <Route path="/categorias" element={<CategoriesPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/favoritos" element={<FavoritesPage />} />
            <Route path="/alertas" element={<AlertsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
