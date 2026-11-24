"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

const NODE_COUNT = 720;
const PARTICLE_COUNT = 240;

function buildBrain() {
  const pos = new Float32Array(NODE_COUNT * 3);
  const col = new Float32Array(NODE_COUNT * 3);
  const cyan = new THREE.Color("#22d3ee");
  const violet = new THREE.Color("#a78bfa");
  const ice = new THREE.Color("#e0f2fe");
  for (let i = 0; i < NODE_COUNT; i++) {
    const side = i % 2 === 0 ? -1 : 1;
    const theta = 2 * Math.PI * Math.random();
    const phi = Math.acos(2 * Math.random() - 1);
    const r = 0.5 + 0.5 * Math.pow(Math.random(), 0.55);
    const x = r * Math.sin(phi) * Math.cos(theta) * 0.52 + side * 0.55;
    const y = r * Math.sin(phi) * Math.sin(theta) * 1.0;
    const z = r * Math.cos(phi) * 1.26;
    pos.set([x, y, z], i * 3);
    const pick = Math.random();
    const c = pick < 0.68 ? cyan : pick < 0.88 ? violet : ice;
    col.set([c.r, c.g, c.b], i * 3);
  }
  // connections between nearby nodes
  const lines: number[] = [];
  const v = new THREE.Vector3();
  for (let i = 0; i < NODE_COUNT; i++) {
    v.set(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]);
    let made = 0;
    for (let j = 0; j < NODE_COUNT && made < 2; j += 7) {
      if (j === i) continue;
      const d = v.distanceTo(new THREE.Vector3(pos[j * 3], pos[j * 3 + 1], pos[j * 3 + 2]));
      if (d > 0.18 && d < 0.52) {
        lines.push(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2], pos[j * 3], pos[j * 3 + 1], pos[j * 3 + 2]);
        made++;
      }
    }
  }
  return { pos, col, lines: new Float32Array(lines) };
}

function buildParticles() {
  const pos = new Float32Array(PARTICLE_COUNT * 3);
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    const theta = 2 * Math.PI * Math.random();
    const phi = Math.acos(2 * Math.random() - 1);
    const r = 2.1 + Math.random() * 1.3;
    pos.set(
      [r * Math.sin(phi) * Math.cos(theta), r * Math.sin(phi) * Math.sin(theta) * 0.8, r * Math.cos(phi)],
      i * 3,
    );
  }
  return pos;
}

function NeuralBrain({ activity, drag }: { activity: number; drag: React.RefObject<{ x: number; y: number }> }) {
  const group = useRef<THREE.Group>(null);
  const particles = useRef<THREE.Points>(null);
  const { pos, col, lines } = useMemo(buildBrain, []);
  const particlePos = useMemo(buildParticles, []);

  useFrame((state, delta) => {
    const g = group.current;
    if (g) {
      g.rotation.y += delta * 0.14 * activity;
      const targetX = drag.current?.x ?? 0;
      g.rotation.x += (targetX - g.rotation.x) * 0.06;
      const s = 1 + Math.sin(state.clock.elapsedTime * (0.9 + activity * 0.7)) * 0.018;
      g.scale.setScalar(s);
    }
    if (particles.current) {
      particles.current.rotation.y -= delta * 0.03 * activity;
      particles.current.rotation.z += delta * 0.008;
    }
  });

  return (
    <>
      <group ref={group}>
        <points>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[pos, 3]} />
            <bufferAttribute attach="attributes-color" args={[col, 3]} />
          </bufferGeometry>
          <pointsMaterial size={0.05} vertexColors transparent opacity={0.95} sizeAttenuation depthWrite={false} blending={THREE.AdditiveBlending} />
        </points>
        <lineSegments>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[lines, 3]} />
          </bufferGeometry>
          <lineBasicMaterial color="#38bdf8" transparent opacity={0.16} blending={THREE.AdditiveBlending} depthWrite={false} />
        </lineSegments>
        <mesh>
          <sphereGeometry args={[0.3, 24, 24]} />
          <meshBasicMaterial color="#22d3ee" transparent opacity={0.13} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
        <mesh>
          <sphereGeometry args={[0.3, 12, 12]} />
          <meshBasicMaterial color="#67e8f9" wireframe transparent opacity={0.22} />
        </mesh>
      </group>
      <points ref={particles}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[particlePos, 3]} />
        </bufferGeometry>
        <pointsMaterial size={0.035} color="#a78bfa" transparent opacity={0.65} sizeAttenuation depthWrite={false} blending={THREE.AdditiveBlending} />
      </points>
    </>
  );
}

export default function Brain3D({ activity = 1 }: { activity?: number }) {
  const drag = useRef({ x: 0, y: 0 });
  const dragging = useRef<{ px: number; py: number } | null>(null);

  return (
    <div
      className="h-full w-full cursor-grab touch-none active:cursor-grabbing"
      onPointerDown={(e) => {
        dragging.current = { px: e.clientX, py: e.clientY };
      }}
      onPointerMove={(e) => {
        if (!dragging.current) return;
        const dy = e.clientY - dragging.current.py;
        drag.current.x = THREE.MathUtils.clamp(drag.current.x + dy * 0.004, -0.9, 0.9);
        dragging.current = { px: e.clientX, py: e.clientY };
      }}
      onPointerUp={() => {
        dragging.current = null;
      }}
      onPointerLeave={() => {
        dragging.current = null;
      }}
    >
      <Canvas camera={{ position: [0, 0.35, 4.7], fov: 55 }} dpr={[1, 1.75]} gl={{ antialias: true, alpha: true }}>
        <NeuralBrain activity={activity} drag={drag} />
      </Canvas>
    </div>
  );
}
