import React, { useState, useEffect } from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';
import useBaseUrl from '@docusaurus/useBaseUrl';

// HomePageHeader with an Interactive Explore Button
function HomepageHeader() {
  const { siteConfig } = useDocusaurusContext();
  const [isHovered, setIsHovered] = useState(false);

  const handleHover = () => setIsHovered(true);
  const handleMouseLeave = () => setIsHovered(false);

  return (
    <header style={headerStyles.heroBanner}>
      <div style={headerStyles.container}>
        <Heading as="h1" style={headerStyles.heroTitle}>
          {siteConfig.title}
        </Heading>
        <p style={headerStyles.heroSubtitle}>{siteConfig.tagline}</p>
        <div>
          <Link
            className={clsx("button button--secondary button--lg", isHovered && 'buttonHovered')}
            to="/docs/intro"
            aria-label="Learn more about SHARC"
            onMouseEnter={handleHover}
            onMouseLeave={handleMouseLeave}
            style={{ ...headerStyles.button, ...(isHovered && headerStyles.buttonHovered) }}
          >
            Explore SHARC
          </Link>
        </div>
      </div>
      {/* Blurred Logo Behind Button */}
      <div style={headerStyles.blurredLogoWrapper}>
        <img
          src={useBaseUrl ("/img/logo.svg")}
          alt="SHARC Logo"
          style={headerStyles.blurredLogo}
        />
      </div>
    </header>
  );
}

function HomepageFeatures() {
  return (
    <section style={featureStyles.homepageFeatures}>
      <h2 style={featureStyles.featureTitle}>Welcome to SHARC</h2>
      <p style={featureStyles.featureDescription}>
        A powerful simulator designed to support SHARing and Compatibility studies of radiocommunication systems.
      </p>
      <div style={featureStyles.featureList}>
        {[
          {
            title: "", 
            description: "",
          },
          { 
            title: "SHARing and Compatibility", 
            description: "SHARC helps users simulate and evaluate various radiocommunication systems to understand how they share and coexist in the radio spectrum.", 
            logo: useBaseUrl ("/img/logo.svg")  
          },
          { 
            title: "", 
            description: "",  
          },
        ].map((feature, index) => (
          <div key={index} style={featureStyles.featureItem}>
            <div style={featureStyles.icon}>
              <img 
                src={feature.logo} 
                alt={`${feature.title} logo`} 
                style={featureStyles.iconImage} 
                className="moving-icon" 
              />
            </div>
            <h3 style={featureStyles.featureItemTitle}>{feature.title}</h3>
            <p style={featureStyles.featureItemDescription}>{feature.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Home(): JSX.Element {
  const { siteConfig } = useDocusaurusContext();

  // Apply styles only on the client side
  useEffect(() => {
    if (typeof document !== 'undefined') {
      const styleSheet = document.styleSheets[0];
      
      styleSheet.insertRule(`@keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
      }`, styleSheet.cssRules.length);

      styleSheet.insertRule(`@keyframes slideUp {
        from { transform: translateY(20px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
      }`, styleSheet.cssRules.length);

      styleSheet.insertRule(`@keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
      }`, styleSheet.cssRules.length);

      styleSheet.insertRule(`.moving-icon {
        animation: moveIcon 2s ease-in-out infinite;
      }`, styleSheet.cssRules.length);
    }
  }, []);

  return (
    <Layout
      title={`Welcome to ${siteConfig.title}`}
      description="Learn about SHARC and how it can help you."
    >
      <HomepageHeader />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}

// Existing header and feature styles
const headerStyles = {
  heroBanner: {
    background: 'linear-gradient(135deg, #007acc, #00b4d8)',
    color: 'white',
    padding: '4rem 0',
    textAlign: 'center' as const,
    animation: 'fadeIn 1s ease-in',
    boxShadow: '0 8px 16px rgba(0, 0, 0, 0.2)',
    borderRadius: '0 0 20px 20px',
    position: 'relative' as const,
    zIndex: 1,
  },
  container: {
    maxWidth: '900px',
    margin: '0 auto',
    animation: 'slideUp 1s ease-in-out',
  },
  heroTitle: {
    fontSize: '3.5rem',
    fontWeight: 'bold',
    margin: 0,
    opacity: 0,
    animation: 'fadeIn 1s forwards',
    animationDelay: '0.3s',
  },
  heroSubtitle: {
    fontSize: '1.75rem',
    color: '#e0f7fa',
    opacity: 0,
    animation: 'fadeIn 1s forwards',
    animationDelay: '0.5s',
  },
  button: {
    fontSize: '1.25rem',
    padding: '1rem 2rem',
    borderRadius: '50px',
    backgroundColor: '#00b4d8',
    color: 'white',
    textDecoration: 'none',
    transition: 'transform 0.3s ease, background-color 0.3s ease, box-shadow 0.3s ease',
    display: 'inline-block',
    marginTop: '1.5rem',
    animation: 'fadeIn 1s forwards',
    animationDelay: '0.7s',
    boxShadow: '0px 4px 12px rgba(0, 0, 0, 0.2)',
  },
  buttonHovered: {
    backgroundColor: '#007acc',
    transform: 'scale(1.05)',
    boxShadow: '0px 6px 16px rgba(0, 0, 0, 0.25)',
    animation: 'pulse 1s infinite',
  },
  blurredLogoWrapper: {
    position: 'absolute' as const,
    top: '0',
    left: '50%',
    transform: 'translateX(-50%)',
    width: '100%',
    height: '100%',
    zIndex: -1,
  },
  blurredLogo: {
    width: '100%',
    height: 'auto',
    filter: 'blur(15px)',
    opacity: '0.2',
  },
};

// Existing feature styles
const featureStyles = {
  homepageFeatures: {
    padding: '4rem 0',
    textAlign: 'center',
    backgroundColor: '#f0f8ff',
    animation: 'fadeIn 1s ease-in-out',
  },
  featureTitle: {
    fontSize: '2.5rem',
    fontWeight: 'bold',
    marginBottom: '1rem',
  },
  featureDescription: {
    fontSize: '1.25rem',
    color: '#555',
    marginBottom: '2rem',
  },
  featureList: {
    display: 'flex',
    justifyContent: 'space-around',
    gap: '2rem',
    flexWrap: 'wrap',
  },
  featureItem: {
    backgroundColor: '#ffffff',
    borderRadius: '10px',
    padding: '2rem',
    boxShadow: '0px 4px 12px rgba(0, 0, 0, 0.1)',
    textAlign: 'center',
    flex: '1 1 30%',
    transition: 'transform 0.3s ease, box-shadow 0.3s ease',
  },
  featureItemTitle: {
    fontSize: '1.5rem',
    fontWeight: 'bold',
    marginBottom: '1rem',
  },
  featureItemDescription: {
    fontSize: '1rem',
    color: '#777',
  },
  icon: {
    marginBottom: '1rem',
  },
  iconImage: {
    width: '70px',
    height: 'auto',
    transition: 'transform 0.3s ease',
  },
};
