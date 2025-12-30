# OCR Document Processor - Frontend

A modern Next.js application for uploading PDF documents and extracting text using OCR technology. This frontend interfaces with a Python FastAPI backend to provide a seamless document processing experience.

## Features

- 📄 **PDF Upload**: Drag-and-drop or click to upload PDF documents
- 🔄 **Real-time Progress**: Track upload progress with visual indicators
- 📊 **Document Management**: View, manage, and delete uploaded documents
- 📝 **Text Extraction**: View extracted text from PDF documents
- 📋 **Copy & Download**: Copy text to clipboard or download as .txt file
- 🎨 **Modern UI**: Clean, responsive design with Tailwind CSS
- ⚡ **Fast Performance**: Built with Next.js 14+ App Router
- 🔒 **Type Safety**: Full TypeScript implementation

## Tech Stack

- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **API Client**: Native Fetch API with XMLHttpRequest for uploads
- **State Management**: React Hooks

## Prerequisites

- Node.js 18+ and npm
- Running FastAPI backend (see `ocr-backend/` directory)

## Installation

1. **Navigate to the frontend directory**:

   ```bash
   cd ocr-frontend
   ```

2. **Install dependencies**:

   ```bash
   npm install
   ```

3. **Configure environment variables**:

   ```bash
   cp .env.local.example .env.local
   ```

4. **Edit `.env.local`** and set the backend URL:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

## Running the Application

### Development Mode

```bash
npm run dev
```

The application will be available at [http://localhost:3000](http://localhost:3000)

### Production Build

```bash
npm run build
npm start
```

### Linting

```bash
npm run lint
```

## Project Structure

```
ocr-frontend/
├── app/
│   ├── layout.tsx              # Root layout with metadata
│   ├── page.tsx                # Home page with upload UI
│   └── documents/
│       └── [id]/
│           └── page.tsx        # Document detail page
├── components/
│   ├── DocumentUpload.tsx      # File upload component with drag-and-drop
│   ├── DocumentList.tsx        # List of uploaded documents
│   ├── DocumentViewer.tsx      # Display extracted text and metadata
│   └── LoadingSpinner.tsx      # Loading indicator
├── lib/
│   ├── api.ts                  # API client for FastAPI backend
│   └── types.ts                # TypeScript type definitions
├── public/                     # Static assets
├── .env.local                  # Environment variables (not in git)
├── .env.local.example          # Environment variables template
├── next.config.ts              # Next.js configuration
├── tailwind.config.ts          # Tailwind CSS configuration
├── tsconfig.json               # TypeScript configuration
└── package.json                # Dependencies and scripts
```

## API Integration

The frontend communicates with the FastAPI backend through the following endpoints:

### Upload Document

```typescript
POST /api/documents/upload
Content-Type: multipart/form-data
Body: { file: File }
```

### Get Document Details

```typescript
GET / api / documents / { id };
Response: DocumentResponse;
```

### Get Extracted Text

```typescript
GET / api / documents / { id } / text;
Response: ExtractedText;
```

### List All Documents

```typescript
GET /api/documents
Response: DocumentResponse[]
```

### Delete Document

```typescript
DELETE / api / documents / { id };
Response: {
  message: string;
}
```

## Components

### DocumentUpload

Handles file upload with drag-and-drop functionality, file validation, and progress tracking.

**Props**:

- `onUploadSuccess?: (documentId: string) => void`
- `onUploadError?: (error: string) => void`

**Features**:

- Drag-and-drop support
- File type validation (PDF only)
- File size validation (max 50MB)
- Upload progress indicator
- Success/error messages

### DocumentList

Displays a list of uploaded documents with metadata and actions.

**Props**:

- `refreshTrigger?: number` - Trigger to refresh the list
- `onDelete?: () => void` - Callback after deletion

**Features**:

- Auto-refresh on upload
- Document metadata display
- Status indicators
- Delete functionality
- Responsive design

### DocumentViewer

Shows document details and extracted text.

**Props**:

- `documentId: string` - ID of the document to display

**Features**:

- Document metadata display
- Extracted text viewer
- Copy to clipboard
- Download as text file
- Confidence score display

### LoadingSpinner

Reusable loading indicator component.

**Props**:

- `size?: 'sm' | 'md' | 'lg'`
- `className?: string`

## Environment Variables

| Variable              | Description         | Default                 |
| --------------------- | ------------------- | ----------------------- |
| `NEXT_PUBLIC_API_URL` | FastAPI backend URL | `http://localhost:8000` |

**Note**: Variables prefixed with `NEXT_PUBLIC_` are exposed to the browser.

## Usage Guide

### Uploading a Document

1. Navigate to the home page
2. Drag and drop a PDF file or click "Choose a PDF file"
3. Wait for the upload to complete
4. The document will appear in the "Recent Documents" list

### Viewing Document Details

1. Click on any document in the list
2. View extracted text and metadata
3. Use "Copy Text" to copy to clipboard
4. Use "Download Text" to save as .txt file

### Deleting a Document

1. Click the delete icon (trash) next to any document
2. Confirm the deletion
3. The document will be removed from the list

## Error Handling

The application includes comprehensive error handling:

- **File Validation**: Only PDF files up to 50MB are accepted
- **Network Errors**: User-friendly error messages for connection issues
- **API Errors**: Displays backend error messages
- **Loading States**: Shows spinners during async operations

## Accessibility

- ARIA labels on interactive elements
- Keyboard navigation support
- Screen reader friendly
- Semantic HTML structure

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Development Tips

### Hot Reload

Next.js provides hot module replacement. Changes to components will reflect immediately.

### Type Checking

Run TypeScript type checking:

```bash
npx tsc --noEmit
```

### Debugging

Use React Developer Tools and browser DevTools for debugging.

## Integration Testing

### Testing with the Backend

Before testing the frontend, ensure the backend is running:

```bash
# In the ocr-backend directory
python -m app.main
```

Or use the automated script from the project root:

```bash
./scripts/start-dev.sh
```

### Manual Integration Tests

#### 1. Test Document Upload Flow

1. **Start both services**:

   ```bash
   # Terminal 1 - Backend
   cd ocr-backend
   source venv/bin/activate
   python -m app.main

   # Terminal 2 - Frontend
   cd ocr-frontend
   npm run dev
   ```

2. **Open the application**:

   - Navigate to http://localhost:3000
   - You should see the upload interface

3. **Upload a document**:

   - Drag and drop a PDF file or click "Choose a PDF file"
   - Watch the upload progress bar
   - Verify success message appears
   - Document should appear in "Recent Documents" list

4. **View extracted text**:

   - Click on the uploaded document
   - Wait for processing to complete (10-30 seconds)
   - Verify extracted text is displayed
   - Check metadata (page count, file size, etc.)

5. **Test actions**:

   - Click "Copy Text" - verify clipboard contains text
   - Click "Download Text" - verify .txt file downloads
   - Click "Back to Documents" - verify navigation works

6. **Test deletion**:
   - Click delete icon on a document
   - Confirm deletion
   - Verify document is removed from list

#### 2. Test Error Handling

**Invalid File Type**:

```bash
# Try uploading a non-PDF file
# Expected: Error message "Only PDF files are supported"
```

**Large File**:

```bash
# Try uploading a file > 50MB
# Expected: Error message about file size limit
```

**Backend Offline**:

```bash
# Stop the backend server
# Try to upload or view documents
# Expected: Network error message
```

#### 3. Test Real-time Updates

1. Upload a document
2. Immediately navigate to document list
3. Verify status shows "pending" or "processing"
4. Refresh after 30 seconds
5. Verify status changes to "completed"

### Automated Integration Testing

Create a test script `test-integration.sh`:

```bash
#!/bin/bash
# Save in ocr-frontend directory

echo "Testing Frontend Integration..."

# Check if backend is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Backend is not running on port 8000"
    exit 1
fi
echo "✓ Backend is running"

# Check if frontend is running
if ! curl -s http://localhost:3000 > /dev/null; then
    echo "❌ Frontend is not running on port 3000"
    exit 1
fi
echo "✓ Frontend is running"

# Test API connectivity from frontend perspective
API_URL=$(grep NEXT_PUBLIC_API_URL .env.local | cut -d'=' -f2)
echo "✓ API URL configured: $API_URL"

# Test health endpoint
HEALTH=$(curl -s $API_URL/health)
if echo "$HEALTH" | grep -q "healthy"; then
    echo "✓ Backend health check passed"
else
    echo "❌ Backend health check failed"
    exit 1
fi

echo ""
echo "✅ All integration checks passed!"
echo ""
echo "Manual testing steps:"
echo "1. Open http://localhost:3000"
echo "2. Upload a PDF document"
echo "3. View extracted text"
echo "4. Test copy and download features"
echo "5. Delete the document"
```

Make it executable and run:

```bash
chmod +x test-integration.sh
./test-integration.sh
```

### Testing Checklist

Use this checklist to verify all features:

- [ ] **Upload**

  - [ ] Drag and drop works
  - [ ] Click to select works
  - [ ] Progress bar displays
  - [ ] Success message shows
  - [ ] Document appears in list

- [ ] **Document List**

  - [ ] Documents load on page load
  - [ ] Status indicators work (pending/completed/failed)
  - [ ] Metadata displays correctly
  - [ ] Click to view works
  - [ ] Delete button works

- [ ] **Document Viewer**

  - [ ] Extracted text displays
  - [ ] Metadata shows correctly
  - [ ] Copy to clipboard works
  - [ ] Download as text works
  - [ ] Back navigation works

- [ ] **Error Handling**

  - [ ] Invalid file type rejected
  - [ ] Large file rejected
  - [ ] Network errors handled
  - [ ] Backend errors displayed

- [ ] **Responsive Design**
  - [ ] Works on desktop
  - [ ] Works on tablet
  - [ ] Works on mobile

### Common Integration Issues

#### Issue: "Failed to fetch documents"

**Cause**: Backend not running or wrong API URL

**Solution**:

```bash
# Check backend status
curl http://localhost:8000/health

# Verify .env.local
cat .env.local | grep NEXT_PUBLIC_API_URL

# Should be: NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### Issue: Upload succeeds but document never completes

**Cause**: Gemini API key issue or processing error

**Solution**:

```bash
# Check backend logs
tail -f ../ocr-backend/backend.log

# Verify Gemini API key
grep GEMINI_API_KEY ../ocr-backend/.env
```

#### Issue: CORS errors in browser console

**Cause**: Backend CORS not configured for frontend URL

**Solution**: Backend should allow `http://localhost:3000` (already configured by default)

#### Issue: Text not copying to clipboard

**Cause**: Browser permissions or HTTPS requirement

**Solution**:

- Ensure you're on `localhost` (not `127.0.0.1`)
- Check browser console for permission errors
- Try a different browser

### Performance Testing

Test with different document sizes:

1. **Small PDF (1-5 pages)**:

   - Expected processing time: 5-10 seconds
   - Should complete without issues

2. **Medium PDF (10-50 pages)**:

   - Expected processing time: 15-30 seconds
   - Monitor progress in backend logs

3. **Large PDF (50-100 pages)**:

   - Expected processing time: 30-60 seconds
   - May require patience

4. **Very Large PDF (100+ pages)**:
   - May take several minutes
   - Consider splitting the document

### Browser Compatibility Testing

Test in multiple browsers:

- [ ] Chrome/Chromium (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)

### Screenshots and Usage Examples

#### Home Page

```
┌─────────────────────────────────────────────────────────┐
│  OCR Document Processor                                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  📄 Drag and drop PDF here                     │    │
│  │     or click to select                         │    │
│  │                                                 │    │
│  │  [Choose a PDF file]                           │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Recent Documents                                       │
│  ┌────────────────────────────────────────────────┐    │
│  │ 📄 sample.pdf          ✓ Completed  [View] [×] │    │
│  │ 📄 contract.pdf        ⏳ Processing [View] [×] │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

#### Document Viewer

```
┌─────────────────────────────────────────────────────────┐
│  ← Back to Documents                                    │
├─────────────────────────────────────────────────────────┤
│  Document: sample.pdf                                   │
│  Status: ✓ Completed                                    │
│  Pages: 10 | Size: 240 KB | Quality: High              │
│                                                          │
│  [Copy Text] [Download Text]                            │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │ --- PAGE 1 ---                                 │    │
│  │                                                 │    │
│  │ This is the extracted text from the PDF...     │    │
│  │                                                 │    │
│  │ --- PAGE 2 ---                                 │    │
│  │                                                 │    │
│  │ More extracted text...                         │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Troubleshooting

### Backend Connection Issues

If you see "Network error occurred" or "Failed to load documents":

1. Ensure the FastAPI backend is running
2. Check the `NEXT_PUBLIC_API_URL` in `.env.local`
3. Verify CORS is configured in the backend
4. Check browser console for detailed errors

### Upload Failures

If uploads fail:

1. Check file size (must be < 50MB)
2. Verify file type is PDF
3. Ensure backend has sufficient storage
4. Check backend logs for errors

### Build Errors

If the build fails:

1. Delete `.next` folder and `node_modules`
2. Run `npm install` again
3. Check for TypeScript errors with `npx tsc --noEmit`

## Performance Optimization

- Images and assets are optimized by Next.js
- Code splitting for faster page loads
- Lazy loading of components
- Efficient state management

## Security Considerations

- File type validation on client and server
- File size limits to prevent abuse
- Environment variables for sensitive data
- No sensitive data in client-side code

## Contributing

1. Follow the existing code style
2. Use TypeScript for type safety
3. Add comments for complex logic
4. Test thoroughly before committing

## License

This project is part of the OCR Document Processor system.

## Support

For issues or questions:

1. Check the troubleshooting section
2. Review backend logs
3. Check browser console for errors
4. Verify environment configuration

## Future Enhancements

- [ ] Batch upload support
- [ ] Document search functionality
- [ ] Advanced filtering and sorting
- [ ] Export to multiple formats
- [ ] User authentication
- [ ] Document annotations
- [ ] OCR language selection
- [ ] Real-time processing status updates
