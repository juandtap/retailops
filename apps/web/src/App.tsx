import AppLayout from "@/components/layout/app-layout";
import { Dashboard, SalesExplorer, ForecastPage, ModelPage, PipelinePage } from "@/pages/main/retailops";
import { Navigate, Route, Routes } from "react-router";
export default function App() {
 return <Routes><Route element={<AppLayout />}><Route index element={<Dashboard/>}/><Route path="sales" element={<SalesExplorer/>}/><Route path="forecasts" element={<ForecastPage/>}/><Route path="model" element={<ModelPage/>}/><Route path="pipelines" element={<PipelinePage/>}/><Route path="*" element={<Navigate to="/" replace/>}/></Route></Routes>;
}
