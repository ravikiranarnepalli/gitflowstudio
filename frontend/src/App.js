import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "@/pages/Dashboard";
import Repositories from "@/pages/Repositories";
import Operations from "@/pages/Operations";
import DeploymentConfig from "@/pages/DeploymentConfig";
import Layout from "@/components/Layout";
import { Toaster } from "@/components/ui/sonner";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/repositories" element={<Repositories />} />
            <Route path="/operations" element={<Operations />} />
            <Route path="/deployment" element={<DeploymentConfig />} />
          </Routes>
        </Layout>
      </BrowserRouter>
      <Toaster position="top-right" />
    </div>
  );
}

export default App;
