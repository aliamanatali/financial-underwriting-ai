"use client";

import React from "react";
import { UnderwritingAnalysis } from "@/lib/types";

interface UnderwritingDashboardProps {
  analysis: UnderwritingAnalysis;
}

export default function UnderwritingDashboard({
  analysis,
}: UnderwritingDashboardProps) {
  const getStatusDisplay = (status: string) => {
    if (status === "PASS") {
      return {
        text: "CRITERIA MET",
        color: "bg-green-100 text-green-800 border-green-300",
        icon: "✓",
      };
    } else {
      return {
        text: "CRITERIA NOT MET",
        color: "bg-red-100 text-red-800 border-red-300",
        icon: "✗",
      };
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return (value * 100).toFixed(2) + "%";
  };

  const historicalNOI = analysis.historical_noi || 0;
  const proFormaNOI = analysis.pro_forma_noi || 0;
  const noiChange = proFormaNOI - historicalNOI;
  const noiChangePercent = historicalNOI > 0 ? (noiChange / historicalNOI) * 100 : 0;

  const historicalCapRate = analysis.historical_cap_rate || 0;
  const proFormaCapRate = analysis.cap_rate || 0;
  const capRateChange = proFormaCapRate - historicalCapRate;

  const occupancyRate = analysis.rent_roll_summary?.occupancy_rate || 0;
  const totalUnits = analysis.property_meta?.total_units || 0;
  const occupiedUnits = analysis.rent_roll_summary?.occupied_units || 0;

  return (
    <div className="space-y-6">
      {/* Header with Property Info */}
      <div className="bg-white rounded-lg shadow-sm p-6 border-l-4 border-blue-500">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          {analysis.property_meta.address}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-600">
          <div>
            <p className="text-gray-500">Year Built</p>
            <p className="font-semibold text-gray-900">{analysis.property_meta.year_built}</p>
          </div>
          <div>
            <p className="text-gray-500">Total Units</p>
            <p className="font-semibold text-gray-900">{totalUnits}</p>
          </div>
          <div>
            <p className="text-gray-500">Occupancy</p>
            <p className="font-semibold text-gray-900">{formatPercent(occupancyRate)}</p>
          </div>
          <div>
            <p className="text-gray-500">Purchase Price</p>
            <p className="font-semibold text-gray-900">
              {formatCurrency(analysis.property_meta.purchase_price)}
            </p>
          </div>
          <div>
            <p className="text-gray-500">Existing Loan</p>
            <p className="font-semibold text-gray-900">
              {formatCurrency(analysis.property_meta.current_loan_balance || 0)}
            </p>
          </div>
          <div>
            <p className="text-gray-500">Existing Loan</p>
            <p className="font-semibold text-gray-900">
              {formatCurrency(analysis.property_meta.current_loan_balance || 0)}
            </p>
          </div>
        </div>
      </div>

      {/* Pass/Fail Status Badge */}
      <div className={`rounded-lg border-2 p-6 ${getStatusDisplay(analysis.pass_fail_status).color}`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold flex items-center gap-2">
              <span className="text-3xl">{getStatusDisplay(analysis.pass_fail_status).icon}</span>
              Qualification Status: {getStatusDisplay(analysis.pass_fail_status).text}
            </h3>
            {analysis.gating_reasons.length > 0 && (
              <div className="mt-3 space-y-1">
                {analysis.gating_reasons.map((reason, idx) => (
                  <p key={idx} className="text-sm">
                    • {reason}
                  </p>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Deal Parameters */}
      {analysis.deal_parameters && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-bold text-gray-900 mb-4">Deal Parameters (Valiance Standards)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-50 p-4 rounded">
              <p className="text-sm text-gray-600">Rent Growth Rate</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatPercent(analysis.deal_parameters.growth_rate)}
              </p>
            </div>
            <div className="bg-gray-50 p-4 rounded">
              <p className="text-sm text-gray-600">Vacancy Rate</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatPercent(analysis.deal_parameters.vacancy_rate)}
              </p>
            </div>
            <div className="bg-gray-50 p-4 rounded">
              <p className="text-sm text-gray-600">Exit Cap Rate</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatPercent(analysis.deal_parameters.exit_cap_rate)}
              </p>
            </div>
            <div className="bg-gray-50 p-4 rounded">
              <p className="text-sm text-gray-600">Loan Amount</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatCurrency(analysis.deal_parameters?.loan_amount || 0)}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Financial Summary - Side by Side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* T12 (Historical) */}
        <div className="bg-white rounded-lg shadow-sm p-6 border-t-4 border-orange-500">
          <h3 className="text-lg font-bold text-gray-900 mb-4 text-orange-700">
            T12 (Historical)
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between pb-2 border-b">
              <span className="text-gray-600">Gross Potential Rent</span>
              <span className="font-semibold">
                {formatCurrency(analysis.rent_roll_summary?.total_annual_rent || 0)}
              </span>
            </div>
            <div className="flex justify-between pb-2 border-b">
              <span className="text-gray-600">Total Expenses</span>
              <span className="font-semibold text-red-600">
                -{formatCurrency(
                  analysis.historical_expenses?.reduce((sum, e) => sum + e.value, 0) || 0
                )}
              </span>
            </div>
            <div className="flex justify-between bg-orange-50 p-3 rounded font-bold text-lg">
              <span>Net Operating Income</span>
              <span className="text-orange-700">{formatCurrency(historicalNOI)}</span>
            </div>
            <div className="flex justify-between pt-2 text-lg font-bold">
              <span>Cap Rate</span>
              <span className="text-orange-700">{formatPercent(historicalCapRate)}</span>
            </div>
          </div>
        </div>

        {/* F12 (Pro Forma) */}
        <div className="bg-white rounded-lg shadow-sm p-6 border-t-4 border-green-500">
          <h3 className="text-lg font-bold text-gray-900 mb-4 text-green-700">
            F12 (Pro Forma)
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between pb-2 border-b">
              <span className="text-gray-600">Gross Potential Rent</span>
              <span className="font-semibold">
                {formatCurrency(
                  analysis.rent_roll.reduce((sum, item) => sum + item.market_rent * 12, 0)
                )}
              </span>
            </div>
            <div className="flex justify-between pb-2 border-b">
              <span className="text-gray-600">Total Expenses</span>
              <span className="font-semibold text-red-600">
                -{formatCurrency(
                  analysis.historical_expenses?.reduce((sum, e) => sum + e.value, 0) || 0
                )}
              </span>
            </div>
            <div className="flex justify-between bg-green-50 p-3 rounded font-bold text-lg">
              <span>Net Operating Income</span>
              <span className="text-green-700">{formatCurrency(proFormaNOI)}</span>
            </div>
            <div className="flex justify-between pt-2 text-lg font-bold">
              <span>Cap Rate</span>
              <span className="text-green-700">{formatPercent(proFormaCapRate)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Upside Potential */}
      <div className="bg-gradient-to-r from-blue-50 to-blue-100 rounded-lg shadow-sm p-6 border-l-4 border-blue-500">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Upside Potential</h3>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <p className="text-gray-600 text-sm mb-2">NOI Upside</p>
            <p className="text-3xl font-bold text-blue-700">
              {formatCurrency(noiChange)}
            </p>
            <p className="text-sm text-gray-600 mt-1">
              {noiChangePercent > 0 ? "+" : ""}{noiChangePercent.toFixed(1)}%
            </p>
          </div>
          <div>
            <p className="text-gray-600 text-sm mb-2">Cap Rate Upside</p>
            <p className="text-3xl font-bold text-blue-700">
              {(capRateChange * 100).toFixed(2)}%
            </p>
            <p className="text-sm text-gray-600 mt-1">
              {historicalCapRate.toFixed(2)}% → {proFormaCapRate.toFixed(2)}%
            </p>
          </div>
        </div>
      </div>

      {/* Rent Roll Summary */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Rent Roll Summary</h3>
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-blue-50 p-4 rounded">
            <p className="text-sm text-gray-600">Total Units</p>
            <p className="text-3xl font-bold text-blue-700">{totalUnits}</p>
          </div>
          <div className="bg-green-50 p-4 rounded">
            <p className="text-sm text-gray-600">Occupied Units</p>
            <p className="text-3xl font-bold text-green-700">{occupiedUnits}</p>
          </div>
          <div className="bg-orange-50 p-4 rounded">
            <p className="text-sm text-gray-600">Occupancy Rate</p>
            <p className="text-3xl font-bold text-orange-700">{formatPercent(occupancyRate)}</p>
          </div>
          <div className="bg-purple-50 p-4 rounded">
            <p className="text-sm text-gray-600">Avg Monthly Rent</p>
            <p className="text-2xl font-bold text-purple-700">
              {formatCurrency(
                analysis.rent_roll_summary?.total_monthly_rent
                  ? analysis.rent_roll_summary.total_monthly_rent / totalUnits
                  : 0
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
