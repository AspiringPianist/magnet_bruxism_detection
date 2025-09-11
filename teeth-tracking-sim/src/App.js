import React, { useState, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Text } from '@react-three/drei';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

function Teeth({ upperPos }) {
  const lower = {
    posX: 0,
    posY: -0.75,  // Bring lower teeth closer to upper teeth
    posZ: 0,
    rotY: 0,
  };

  return (
    <>
      {/* Upper teeth box */}
      <mesh position={[upperPos.x, upperPos.y, upperPos.z]} rotation={[0, 0, 0]}>
        <boxGeometry args={[4, 0.5, 0.5]} />
        <meshStandardMaterial color="red" />
        {/* Magnet sphere */}
        <mesh position={[0, -0.3, 0]}>
          <sphereGeometry args={[0.2, 32, 32]} />
          <meshStandardMaterial color="yellow" />
          <Text
            position={[0, -0.3, 0]}
            fontSize={0.3}
            color="yellow"
            anchorX="center"
            anchorY="middle"
          >
            Magnet
          </Text>
        </mesh>
      </mesh>

      {/* Lower teeth box */}
      <mesh position={[lower.posX, lower.posY, lower.posZ]} rotation={[0, lower.rotY, 0]}>
        <boxGeometry args={[4, 0.5, 0.5]} />
        <meshStandardMaterial color="blue" />
        {/* IMU sphere */}
        <mesh position={[0, 0.3, 0]}>
          <sphereGeometry args={[0.2, 32, 32]} />
          <meshStandardMaterial color="lime" />
          <Text
            position={[0, 0.3, 0]}
            fontSize={0.3}
            color="lime"
            anchorX="center"
            anchorY="middle"
          >
            Magnetometer
          </Text>
        </mesh>
      </mesh>
    </>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    fetch('/simulation_data.json')
      .then(response => response.json())
      .then(json => setData(json));
  }, []);

  useEffect(() => {
    if (!data || !isPlaying) return;
    const interval = setInterval(() => {
      setCurrentIndex(prev => (prev + 5) % data.t.length); // Skip 5 data points for 15-second playback
    }, 100); // 100ms intervals, skipping data points to maintain 15-second total time
    return () => clearInterval(interval);
  }, [data, isPlaying]);

  if (!data) return <div>Loading...</div>;

  const upperPos = {
    x: data.true_positions[currentIndex][0] * 50,  // Scale up movement for visibility (50x)
    y: 1 + data.true_positions[currentIndex][2] * 50,  // Base position + scaled vertical movement
    z: data.true_positions[currentIndex][1] * 50   // Scale up lateral movement
  };

  const chartData = data.t.slice(0, currentIndex + 1).map((t, i) => ({
    time: t,
    Bx: data.noisy_B[i][0] * 1e6,
    By: data.noisy_B[i][1] * 1e6,
    Bz: data.noisy_B[i][2] * 1e6,
    magnitude: data.field_magnitude[i]
  }));

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Canvas camera={{ position: [0, 0, 5] }} background="black" style={{ flex: 1 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 10, 7]} />
        <OrbitControls />
        <Teeth upperPos={upperPos} />
      </Canvas>
      <div style={{ height: '300px', background: 'white' }}>
        <button onClick={() => setIsPlaying(!isPlaying)}>
          {isPlaying ? 'Pause' : 'Play'}
        </button>
        <LineChart width={800} height={250} data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="Bx" stroke="#8884d8" />
          <Line type="monotone" dataKey="By" stroke="#82ca9d" />
          <Line type="monotone" dataKey="Bz" stroke="#ffc658" />
          <Line type="monotone" dataKey="magnitude" stroke="#ff0000" />
        </LineChart>
      </div>
    </div>
  );
}
