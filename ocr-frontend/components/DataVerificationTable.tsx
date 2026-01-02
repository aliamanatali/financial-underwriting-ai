"use client";

import { useState } from "react";

export interface NormalizedDataItem {
  id: string;
  raw_text: string;
  normalized_value: string;
  field_type: string;
  confidence: number;
  user_verified: boolean;
  user_correction?: string | null;
  source_document: string;
}

interface DataVerificationTableProps {
  items: NormalizedDataItem[];
  availableCategories: string[];
  onVerify: (itemId: string, userCorrection?: string) => void;
  onVerifyAll: () => void;
}

export default function DataVerificationTable({
  items,
  availableCategories,
  onVerify,
  onVerifyAll,
}: DataVerificationTableProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");

  const handleEdit = (item: NormalizedDataItem) => {
    setEditingId(item.id);
    setEditValue(item.user_correction || item.normalized_value);
  };

  const handleSave = (itemId: string) => {
    const originalItem = items.find((i) => i.id === itemId);
    if (originalItem && editValue !== originalItem.normalized_value) {
      onVerify(itemId, editValue);
    } else {
      onVerify(itemId);
    }
    setEditingId(null);
    setEditValue("");
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditValue("");
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.95) return "text-green-600 bg-green-50";
    if (confidence >= 0.85) return "text-yellow-600 bg-yellow-50";
    return "text-red-600 bg-red-50";
  };

  const verifiedCount = items.filter((item) => item.user_verified).length;
  const totalCount = items.length;
  const progressPercentage = totalCount > 0 ? (verifiedCount / totalCount) * 100 : 0;

  return (
    <div className="space-y-4">
      {/* Header with Progress */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              Data Verification
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              Review and correct AI-mapped categories
            </p>
          </div>
          <button
            onClick={onVerifyAll}
            disabled={verifiedCount === totalCount}
            className={`px-4 py-2 rounded-md font-medium ${
              verifiedCount === totalCount
                ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            Verify All
          </button>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-gray-600">
            <span>
              Verified: {verifiedCount} / {totalCount}
            </span>
            <span>{progressPercentage.toFixed(0)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-blue-600 h-3 rounded-full transition-all duration-300"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
        </div>
      </div>

      {/* Split-Screen Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Source Document
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Raw Text (PDF)
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Mapped Category
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Confidence
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={`${
                    item.user_verified ? "bg-green-50" : "hover:bg-gray-50"
                  }`}
                >
                  {/* Source Document */}
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {item.source_document}
                  </td>

                  {/* Raw Text */}
                  <td className="px-6 py-4 text-sm text-gray-900">
                    <div className="max-w-xs">
                      <span className="font-mono bg-gray-100 px-2 py-1 rounded">
                        {item.raw_text}
                      </span>
                    </div>
                  </td>

                  {/* Mapped Category */}
                  <td className="px-6 py-4 text-sm">
                    {editingId === item.id ? (
                      <select
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        autoFocus
                      >
                        {availableCategories.map((category) => (
                          <option key={category} value={category}>
                            {category}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="flex items-center space-x-2">
                        <span
                          className={`font-medium ${
                            item.user_correction
                              ? "text-blue-600"
                              : "text-gray-900"
                          }`}
                        >
                          {item.user_correction || item.normalized_value}
                        </span>
                        {item.user_correction && (
                          <span className="text-xs text-blue-600 bg-blue-100 px-2 py-0.5 rounded">
                            Corrected
                          </span>
                        )}
                      </div>
                    )}
                  </td>

                  {/* Confidence */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getConfidenceColor(
                        item.confidence
                      )}`}
                    >
                      {(item.confidence * 100).toFixed(0)}%
                    </span>
                  </td>

                  {/* Status */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    {item.user_verified ? (
                      <span className="inline-flex items-center text-green-600">
                        <svg
                          className="w-5 h-5 mr-1"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fillRule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                            clipRule="evenodd"
                          />
                        </svg>
                        Verified
                      </span>
                    ) : (
                      <span className="text-gray-500 text-sm">Pending</span>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {editingId === item.id ? (
                      <div className="flex space-x-2">
                        <button
                          onClick={() => handleSave(item.id)}
                          className="text-green-600 hover:text-green-900 font-medium"
                        >
                          Save
                        </button>
                        <button
                          onClick={handleCancel}
                          className="text-gray-600 hover:text-gray-900 font-medium"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="flex space-x-2">
                        {!item.user_verified && (
                          <>
                            <button
                              onClick={() => handleEdit(item)}
                              className="text-blue-600 hover:text-blue-900 font-medium"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => onVerify(item.id)}
                              className="text-green-600 hover:text-green-900 font-medium"
                            >
                              ✓ Verify
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Legend */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-700 mb-2">
          Confidence Levels:
        </h3>
        <div className="flex space-x-4 text-xs">
          <div className="flex items-center">
            <span className="inline-block w-3 h-3 bg-green-600 rounded-full mr-1"></span>
            <span className="text-gray-600">High (≥95%)</span>
          </div>
          <div className="flex items-center">
            <span className="inline-block w-3 h-3 bg-yellow-600 rounded-full mr-1"></span>
            <span className="text-gray-600">Medium (85-94%)</span>
          </div>
          <div className="flex items-center">
            <span className="inline-block w-3 h-3 bg-red-600 rounded-full mr-1"></span>
            <span className="text-gray-600">Low (&lt;85%)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
