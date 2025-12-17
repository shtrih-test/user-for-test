// @ts-check
import {themes as prismThemes} from 'prism-react-renderer';

// Для GitHub Pages берём из env переменных
const url = process.env.DOCUSAURUS_URL || 'http://localhost';
const baseUrl = process.env.DOCUSAURUS_BASE_URL || '/';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'SWOT Analyzer',
  tagline: 'Стратегический анализ с версионированием',
  favicon: 'img/favicon.ico',

  url: url,
  baseUrl: baseUrl,

  onBrokenLinks: 'warn',
  onBrokenMarkdownLinks: 'warn',

  i18n: {
    defaultLocale: 'ru',
    locales: ['ru'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          routeBasePath: '/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      navbar: {
        title: '🎯 SWOT Analyzer',
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'swotSidebar',
            position: 'left',
            label: 'Анализы',
          },
          {
            href: '/comparisons',
            label: 'Сравнения',
            position: 'left',
          },
        ],
      },
      footer: {
        style: 'dark',
        copyright: `SWOT Analyzer © ${new Date().getFullYear()}`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
      colorMode: {
        defaultMode: 'light',
        disableSwitch: false,
      },
    }),
};

export default config;
