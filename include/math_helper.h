#pragma once

#include "math.h"

#include "quat.h"

#include <Eigen/Core>

static const Eigen::Matrix<double, 2, 3> I_2x3 = [] {
  Eigen::Matrix<double, 2, 3> tmp;
  tmp << 1.0, 0, 0,
         0, 1.0, 0;
  return tmp;
}();

static const Eigen::Matrix3d I_3x3 = [] {
  Eigen::Matrix3d tmp = Eigen::Matrix3d::Identity();
  return tmp;
}();

static const Eigen::Matrix2d I_2x2 = [] {
  Eigen::Matrix2d tmp = Eigen::Matrix2d::Identity();
  return tmp;
}();


static const Eigen::Vector3d e_x = [] {
  Eigen::Vector3d tmp;
  tmp << 1.0, 0, 0;
  return tmp;
}();

static const Eigen::Vector3d e_y = [] {
  Eigen::Vector3d tmp;
  tmp << 0, 1.0, 0;
  return tmp;
}();

static const Eigen::Vector3d e_z = [] {
  Eigen::Vector3d tmp;
  tmp << 0, 0, 1.0;
  return tmp;
}();

void removeRow(Eigen::MatrixXd& matrix, unsigned int rowToRemove)
{
    unsigned int numRows = matrix.rows()-1;
    unsigned int numCols = matrix.cols();

    if( rowToRemove < numRows )
        matrix.block(rowToRemove,0,numRows-rowToRemove,numCols) = matrix.bottomRows(numRows-rowToRemove);

    matrix.conservativeResize(numRows,numCols);
}

void removeColumn(Eigen::MatrixXd& matrix, unsigned int colToRemove)
{
    unsigned int numRows = matrix.rows();
    unsigned int numCols = matrix.cols()-1;

    if( colToRemove < numCols )
        matrix.block(0,colToRemove,numRows,numCols-colToRemove) = matrix.rightCols(numCols-colToRemove);

    matrix.conservativeResize(numRows,numCols);
}

inline Eigen::Matrix3d skew(const Eigen::Vector3d v)
{
  Eigen::Matrix3d mat;
  mat << 0.0, -v(2), v(1),
         v(2), 0.0, -v(0),
         -v(1), v(0), 0.0;
  return mat;
}

inline Eigen::Matrix<double, 3, 2> T_zeta(quat::Quaternion q)
{
  return q.doublerot(I_2x3.transpose());
}

inline Eigen::Vector2d q_feat_boxminus(quat::Quaternion q0, quat::Quaternion q1)
{
  Eigen::Vector3d zeta0 = q0.rot(e_z);
  Eigen::Vector3d zeta1 = q1.rot(e_z);

  Eigen::Vector2d dq;
  if ((zeta0 - zeta1).norm() > 1e-16)
  {
    Eigen::Vector3d v = zeta1.cross(zeta0);
    v /= v.norm();
    double theta = std::acos(zeta1.dot(zeta0));
    dq = theta * T_zeta(q1).transpose() * v;
  }
  else
  {
    dq.setZero();
  }
  return dq;
}

inline quat::Quaternion q_feat_boxplus(quat::Quaternion q, Eigen::Vector2d dq)
{
  return quat::Quaternion::exp(T_zeta(q) * dq) * q;
}


void concatenate_SE2(Eigen::Vector3d& T1, Eigen::Vector3d& T2, Eigen::Vector3d& Tout)
{
  double cs = std::cos(T1(2,0));
  double ss = std::sin(T1(2,0));
  Tout(0) = T1(0) + T2(0) * cs - T2(1) * ss;
  Tout(1) = T1(1) + T2(0) * ss + T2(1) * cs;
  double psi= T1(2) + T2(2);
  if (psi > M_PI)
      psi -= 2.*M_PI;
  else if (psi < -M_PI)
      psi += 2.*M_PI;
  Tout(2) = psi;
}


void invert_SE2(Eigen::Vector3d& T, Eigen::Vector3d& Tout)
{
  double cs = std::cos(T(2));
  double ss = std::sin(T(2));
  Tout(0) = -(T(0) * cs + T(1) * ss);
  Tout(1) = -(- T(0) * ss + T(1) * cs);
  Tout(2) = -T(2);
}
