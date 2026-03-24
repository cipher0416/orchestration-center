# A2A-T Prototype: Workflow Designer & Agent Registry

A modern, high-performance orchestration platform for multi-agent systems. This prototype provides a visual interface for designing workflows and managing agent registries.

## 🚀 Features

- **Visual Workflow Designer**: Drag-and-drop interface for building complex agent orchestrations, powered by [React Flow](https://reactflow.dev/).
- **Automatic Layout**: Integrated [Dagre](https://github.com/dagrejs/dagre) engine for smart, automatic node positioning and graph organization.
- **Data Transformation**: Seamless conversion between visual graph representations and structured PSOP JSON workflow definitions.
- **Agent Registry**: Centralized management for agent profiles and configurations.
- **Theme Support**: Seamless switching between Dark and Light modes.
- **Internationalization**: Full support for English and Chinese (Mandarin).
- **Modern Tech Stack**: Built with Vite, React, and Tailwind CSS for a fast and responsive experience.

## 🛠 Tech Stack

- **Framework**: [React 18](https://reactjs.org/)
- **Bundler**: [Vite](https://vitejs.dev/)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/)
- **Graph Engine**: [@xyflow/react (React Flow)](https://reactflow.dev/)
- **Animations**: [Framer Motion](https://www.framer.com/motion/)
- **I18n**: [i18next](https://www.i18next.com/)
- **Testing**: [Vitest](https://vitest.dev/)

## 📦 Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) (version 18 or higher recommended)
- [Yarn](https://yarnpkg.com/) or [npm](https://www.npmjs.com/)

### Installation

```bash
# Clone the repository and navigate to the directory
cd workflow-designer

# Install dependencies
yarn install
```

### Development

```bash
# Start the development server
yarn dev
```

### Build

```bash
# Build for production
yarn build

# Preview production build
yarn preview
```

## 📂 Project Structure

- `src/components/orchestration_center`: Core workflow designer implementation.
- `src/components/registry_center`: Agent registry management components.
- `src/locales`: Translation files for i18n.
- `src/service`: API client and services.

## 🧪 Testing

```bash
# Run unit tests with coverage
yarn coverage
```

---

*Part of the Orchestration Center project.*
