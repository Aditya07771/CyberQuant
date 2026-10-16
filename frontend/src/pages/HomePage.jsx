import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../components/layout/Header';
import { HeroSection } from '../components/home/HeroSection';
import { AboutSection } from '../components/home/AboutSection';
import { DatasetUploadBox } from '../components/home/DatasetUploadBox';
import { ProcessingOverlay } from '../components/home/ProcessingOverlay';
import { useDataset } from '../context/DatasetContext';
import { Shield } from 'lucide-react';

export const HomePage = () => {
  const navigate = useNavigate();
  const { setDatasetLoaded } = useDataset();
  const [isProcessing, setIsProcessing] = useState(false);

  const scrollToUpload = () => {
    const el = document.getElementById('upload-section');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleStartProcessing = () => {
    setIsProcessing(true);
  };

  const handleSuccess = (result) => {
    setDatasetLoaded({
      assetCount: result?.asset_count,
      sessionId: result?.session_id,
      processedAt: result?.processed_at,
      excelSummary: result?.excel_summary || null,
    });
    // Smooth transition
    setTimeout(() => {
      setIsProcessing(false);
      navigate('/insights');
    }, 600);
  };

  const handleError = () => {
    setIsProcessing(false);
  };

  return (
    <div className="min-h-screen flex flex-col font-sans theme-transition bg-th-bg">
      {/* Top Navbar */}
      <Header />

      {/* Main Landing Content */}
      <main className="flex-1 space-y-fluid-md">
        <HeroSection
          onScrollToUpload={scrollToUpload}
          onQuickDemo={() => {
            const el = document.getElementById('upload-section');
            if (el) el.scrollIntoView({ behavior: 'smooth' });
          }}
          isProcessingDemo={isProcessing}
        />

        <DatasetUploadBox
          onStartProcessing={handleStartProcessing}
          onSuccess={handleSuccess}
          onError={handleError}
          isProcessing={isProcessing}
        />

        <AboutSection />
      </main>

      {/* Simulation Progress Overlay */}
      <ProcessingOverlay isVisible={isProcessing} />

      {/* Modern Editorial Footer */}
      <footer className="border-t border-th-border bg-th-surface py-12 text-sm text-th-text-secondary mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-start justify-between">
            {/* Brand & Copyright */}
            <div className="space-y-3">
              <div className="flex items-center space-x-2.5">
                <div className="w-6 h-6 rounded bg-th-brand flex items-center justify-center text-white">
                  <Shield className="w-3.5 h-3.5" />
                </div>
                <span className="font-semibold text-th-text-primary font-serif">CyberRisk Platform</span>
              </div>
              <p className="text-th-text-muted text-xs">
                &copy; {new Date().getFullYear()} CyberRisk Inc. All rights reserved.
              </p>
            </div>

            {/* Resources Links */}
            <div className="flex flex-col space-y-2 md:items-center">
              <h4 className="text-th-text-primary font-semibold mb-1">Resources</h4>
              <a href="#" className="hover:text-th-brand transition-colors text-xs">Documentation</a>
              <a href="#" className="hover:text-th-brand transition-colors text-xs">Open FAIR™ Methodology</a>
              <a href="#" className="hover:text-th-brand transition-colors text-xs">API Reference</a>
            </div>

            {/* Legal Links */}
            <div className="flex flex-col space-y-2 md:items-end">
              <h4 className="text-th-text-primary font-semibold mb-1">Legal</h4>
              <a href="#" className="hover:text-th-brand transition-colors text-xs">Privacy Policy</a>
              <a href="#" className="hover:text-th-brand transition-colors text-xs">Terms of Service</a>
              <a href="#" className="hover:text-th-brand transition-colors text-xs">Security Assurance</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default HomePage;
