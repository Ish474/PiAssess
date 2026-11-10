import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import AppLayout from "./components/layout/AppLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import StudentsPage from "./pages/StudentsPage";
import AcademicsPage from "./pages/AcademicsPage";
import ExamsPage from "./pages/ExamsPage";
import ExamPaperPage from "./pages/ExamPaperPage";
import DocumentsPage from "./pages/DocumentsPage";
import SettingsPage from "./pages/SettingsPage";
import QuestionBankPage from "./pages/QuestionBankPage";
import { GeneratorWizard } from "./pages/aigenerator/GeneratorWizard";
import OmrDesignerPage from "./pages/OmrDesignerPage";
import OmrProcessingPage from "./pages/OmrProcessingPage";
import ResultsPage from "./pages/ResultsPage";
import { Spinner } from "./components/ui";

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="flex min-h-screen items-center justify-center bg-cream">
        <Spinner className="h-7 w-7" />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <Protected>
                <AppLayout />
              </Protected>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/students" element={<StudentsPage />} />
            <Route path="/academics" element={<AcademicsPage />} />
            <Route path="/exams" element={<ExamsPage />} />
            <Route path="/exams/:id" element={<ExamPaperPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/ai-generator" element={<GeneratorWizard />} />
            <Route path="/question-bank" element={<QuestionBankPage />} />
            <Route path="/omr-designer" element={<OmrDesignerPage />} />
            <Route path="/omr-processing" element={<OmrProcessingPage />} />
            <Route path="/results" element={<ResultsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
