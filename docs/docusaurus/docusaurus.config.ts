import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import BrowserOnly from '@docusaurus/BrowserOnly';

const config: Config = {
  title: ' SHARC ',
  tagline: 'A simulator for use in SHARing and Compatibility studies of radiocommunication systems.',
  favicon: 'img/favicon.ico',

  // Set the production url of your site here
  url: 'https://radio-spectrum.github.io',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/SHARC/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'Radio-Spectrum', // Usually your GitHub org/user name.
  projectName: 'SHARC', // Usually your repo name.
  deploymentBranch: 'documentation',
  trailingSlash: false,

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/facebook/docusaurus/tree/main/packages/create-docusaurus/templates/shared/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl:
            'https://github.com/facebook/docusaurus/tree/main/packages/create-docusaurus/templates/shared/',
          // Useful options to enforce blogging best practices
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/sharc-social-card.jpg',
    navbar: {
      title: 'Radio-Spectrum SHARC',
      logo: {
        alt: 'SHARC logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          sidebarId: 'aboutSidebar',
          position: 'left',
          type: 'docSidebar',
          label: 'About',
        },
        {
          sidebarId: 'downloadSidebar',
          positon: 'left',
          href: 'https://github.com/Radio-Spectrum/SHARC/archive/refs/heads/development.zip',
          label: 'Download',
        },
        
        {
          to: 'docs/Contributing',
          sidebarId: 'troubleshootingSidebar',
          positon: 'left',
          label: 'Contributing',
        },
        
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'About',
              to: '/docs/intro',
            },
            
            {
              label: 'Download',
              href: 'https://github.com/Radio-Spectrum/SHARC/archive/refs/heads/development.zip'
            },

            {
              label: 'Troubleshooting',
              to: '/docs/Contributing'
            },
            
          ],
        },
        {
          title: 'References',
          items: [
            {
              label: 'Radio-Spectrum',
              href: 'https://github.com/Radio-Spectrum',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/Radio-Spectrum/SHARC',
            },
          ],
        },
      ],
      copyright: `${new Date().getFullYear()} Radio-Spectrum SHARC.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
