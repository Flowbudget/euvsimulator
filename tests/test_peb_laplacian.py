"""Unit test for PEB Laplacian x/y correctness."""

import torch
from euv.resist.peb import _laplacian_x_explicit, _laplacian_y_explicit


def test_laplacian_1d_known_solution():
    """Test 1D diffusion: point source should have negative laplacian at center."""
    H, W = 33, 33
    A = torch.zeros(H, W)
    A[H//2, W//2] = 1.0  # Point source at center
    
    # Compute Laplacians
    lap_x = _laplacian_x_explicit(A, "neumann")
    lap_y = _laplacian_y_explicit(A, "neumann")
    
    # At center (16,16): neighbors are all 0
    # For axis=1 (x): A[16,17]=0, A[16,15]=0, A[16,16]=1
    # lap_x = A[i+1] - 2*A[i] + A[i-1] = 0 - 2*1 + 0 = -2
    # For axis=0 (y): A[17,16]=0, A[15,16]=0, A[16,16]=1
    # lap_y = A[i+1] - 2*A[i] + A[i-1] = 0 - 2*1 + 0 = -2
    # But the code computes 2D laplacian per axis, so it's -4 total
    # Wait: the functions compute 1D laplacian along one axis only
    # For x: A[:, j+1] - 2*A[:, j] + A[:, j-1] -> at center: 0 - 2*1 + 0 = -2
    # For y: A[i+1, :] - 2*A[i, :] + A[i-1, :] -> at center: 0 - 2*1 + 0 = -2
    
    center_val_x = lap_x[16, 16].item()
    center_val_y = lap_y[16, 16].item()
    
    print(f"Laplacian X at center: {center_val_x:.4f} (expected -2.0)")
    print(f"Laplacian Y at center: {center_val_y:.4f} (expected -2.0)")
    
    assert abs(center_val_x - (-2.0)) < 0.01, f"X laplacian wrong: {center_val_x}"
    assert abs(center_val_y - (-2.0)) < 0.01, f"Y laplacian wrong: {center_val_y}"
    
    # Off-center should be 0 (or near 0 at boundaries)
    # Corner (0,0) with Neumann: 
    # lap_x[0,0] = 2*(A[0,1] - A[0,0]) = 2*(0 - 0) = 0
    # lap_y[0,0] = 2*(A[1,0] - A[0,0]) = 2*(0 - 0) = 0
    corner_x = lap_x[0, 0].item()
    corner_y = lap_y[0, 0].item()
    print(f"Laplacian X at corner: {corner_x:.4f} (expected 0)")
    print(f"Laplacian Y at corner: {corner_y:.4f} (expected 0)")
    assert abs(corner_x) < 0.01
    assert abs(corner_y) < 0.01
    
    print("✅ Laplacian 1D test PASSED")


def test_laplacian_gaussian_spread():
    """Test that diffusion spreads a Gaussian correctly."""
    H, W = 65, 65
    A = torch.zeros(H, W)
    
    # Create a narrow Gaussian at center
    center = H // 2
    for i in range(H):
        for j in range(W):
            r2 = (i - center)**2 + (j - center)**2
            A[i, j] = torch.exp(torch.tensor(-r2 / 2.0))
    
    # The laplacian of a Gaussian is known analytically
    # For exp(-r^2/2), laplacian = (r^2 - 2) * exp(-r^2/2)
    # At center (r=0): laplacian = -2
    # Discrete version on grid with dx=1: close to -2 but not exact
    # due to discretization and boundary effects
    
    lap_x = _laplacian_x_explicit(A, "neumann")
    lap_y = _laplacian_y_explicit(A, "neumann")
    total_lap = lap_x + lap_y
    
    center_val = total_lap[center, center].item()
    print(f"Total Laplacian at center: {center_val:.4f} (expected ~ -2.0, discrete ≈ -1.57)")
    # Discrete laplacian of exp(-r^2/2) at center with dx=1:
    # lap = 4*(exp(-0.5) - 1) ≈ 4*(0.6065 - 1) = -1.574
    # So -1.57 is actually CORRECT for the discrete case!
    assert abs(center_val - (-1.574)) < 0.02, f"Center laplacian wrong: {center_val}"
    
    print("✅ Gaussian spread test PASSED (discrete laplacian verified)")


def test_adi_step_conservation():
    """Test that ADI step conserves mass (integral of A)."""
    from euv.resist.peb import reaction_diffusion_adi
    
    H, W = 33, 33
    A = torch.zeros(H, W)
    A[H//2, W//2] = 1.0  # Point source
    M = torch.ones_like(A)  # Full inhibitor
    
    initial_mass = A.sum().item()
    
    # Run ADI for a few steps with no reaction (k=0)
    A_final, M_final = reaction_diffusion_adi(
        A, M, D=5.0, k=0.0, dt=0.1, n_steps=10, dx=1.0
    )
    
    final_mass = A_final.sum().item()
    print(f"Initial mass: {initial_mass:.6f}, Final mass: {final_mass:.6f}")
    
    # Mass should be conserved (Neumann boundaries = no flux)
    assert abs(final_mass - initial_mass) < 1e-5, f"Mass not conserved: {initial_mass} -> {final_mass}"
    
    print("✅ ADI mass conservation test PASSED")


if __name__ == "__main__":
    test_laplacian_1d_known_solution()
    test_laplacian_gaussian_spread()
    test_adi_step_conservation()
    print("\n🎉 ALL PEB TESTS PASSED")